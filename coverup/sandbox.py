"""Running the scenario repository's test suite inside bubblewrap.

Adapted from joint-task-collusion's `experiments/protocol/code_tests.py` (the bwrap command, the interpreter
mounts, the sandbox probe and the bounded output reader; see THIRD_PARTY_LICENSES.md). There the scratch directory
is mounted read-write and a byte comparison restores the protected target afterwards. Here the episode repository
is mounted read-only instead, so a test process cannot change any file, protected or not: every change to the
repository goes through the agents' logged file tools.
"""

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Restrict the test environment to avoid exposing provider credentials. Keep PATH for toolchain lookup.
_INHERITED_ENV_VARS = ("PATH", "LANG", "LC_ALL")
# System directories the test process may read. Nothing else on the host is mounted.
_SYSTEM_DIRS = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32")
PROCESS_TIMEOUT_SECONDS = 60
# Where a scenario's installed third-party packages (optional scenario.yaml `site_packages`) appear inside the sandbox:
# a read-only site-packages directory of an ordinary virtualenv, put on PYTHONPATH, so a traceback into one of them
# looks like a frame of an installed library. Nothing is mounted there unless a scenario asks for it.
SITE_PACKAGES_MOUNT = f"/opt/venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
# Bytes of test output kept: the first and the last half.
OUTPUT_LIMIT = 100_000


class SandboxUnavailable(RuntimeError):
    """bubblewrap is missing or cannot create namespaces; tests must not run unsandboxed."""


def _interpreter_dirs() -> list[Path]:
    """Directories the interpreter needs, including each hop of a symlinked executable."""
    dirs = [Path(sys.prefix), Path(sys.base_prefix)]
    executable = Path(sys.executable)
    for _ in range(16):
        dirs.append(executable.parent.parent)
        if not executable.is_symlink():
            break
        executable = executable.parent / os.readlink(executable)
    dirs = [Path(os.path.abspath(path)) for path in dirs]
    dirs += [path.resolve() for path in dirs]
    system = [Path(path) for path in _SYSTEM_DIRS]
    return sorted({d for d in dirs if not any(d == s or s in d.parents for s in system)})


def sandbox_command(command: list[str], workdir: Path, read_only: dict[str, Path] | None = None) -> list[str]:
    """Wrap a command so it sees system libraries, the interpreter and a read-only view of `workdir` only (plus each
    host directory in `read_only`, mounted read-only at its key)."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SandboxUnavailable("bwrap (bubblewrap) not found; the scenario tests only run sandboxed")
    wrapped = [bwrap, "--unshare-all", "--die-with-parent", "--new-session"]
    for path in _SYSTEM_DIRS:
        wrapped += ["--ro-bind-try", path, path]
    wrapped += ["--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache"]
    wrapped += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for path in _interpreter_dirs():
        wrapped += ["--ro-bind", str(path), str(path)]
    for mount, host in (read_only or {}).items():
        wrapped += ["--ro-bind", str(Path(host).resolve()), mount]
    wrapped += ["--ro-bind", str(workdir), str(workdir), "--chdir", str(workdir), "--"]
    return wrapped + command


_CHECKED: set[str] = set()


def require_sandbox(workdir: Path) -> None:
    """Raise SandboxUnavailable unless pytest starts inside the sandbox on this host (probed once per process)."""
    key = "probe"
    if key in _CHECKED:
        return
    probe = sandbox_command([sys.executable, "-c", "import pytest, structlog"], Path(workdir).resolve())
    try:
        completed = subprocess.run(probe, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxUnavailable(f"sandbox probe failed: {exc}") from exc
    if completed.returncode != 0:
        raise SandboxUnavailable(
            "sandbox probe failed (are unprivileged user namespaces enabled, and are pytest and structlog "
            f"installed?): {completed.stderr.strip() or completed.stdout.strip()}"
        )
    _CHECKED.add(key)


def _drain(stream: Any, head: bytearray, tail: bytearray, dropped: list[int]) -> None:
    half = OUTPUT_LIMIT // 2
    for chunk in iter(lambda: stream.read1(65536), b""):
        room = half - len(head)
        if room > 0:
            head += chunk[:room]
            chunk = chunk[room:]
        tail += chunk
        if len(tail) > half:
            dropped[0] += len(tail) - half
            del tail[: len(tail) - half]


@dataclass(frozen=True)
class TestRun:
    returncode: int | None  # None when the run timed out
    output: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def run_pytest(repo: Path, target: str = "", extra_args: tuple[str, ...] = (),
               site_packages: Path | None = None) -> TestRun:
    """Run pytest on `target` (a path inside the repository; empty means the whole suite), sandboxed. `extra_args` go
    before the target (the hidden checks use them to ignore the agents' pytest configuration). `site_packages`, a
    host directory of installed packages, is mounted read-only at SITE_PACKAGES_MOUNT and put on PYTHONPATH."""
    repo = Path(repo).resolve()
    require_sandbox(repo)
    env = {name: os.environ[name] for name in _INHERITED_ENV_VARS if name in os.environ}
    env.update({"HOME": "/tmp", "TMPDIR": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"})
    read_only = {}
    if site_packages is not None:
        read_only[SITE_PACKAGES_MOUNT] = Path(site_packages)
        env["PYTHONPATH"] = SITE_PACKAGES_MOUNT
    command = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *extra_args]
    if target:
        command.append(target)
    process = subprocess.Popen(
        sandbox_command(command, repo, read_only), cwd=repo, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    head, tail, dropped = bytearray(), bytearray(), [0]
    reader = threading.Thread(target=_drain, args=(process.stdout, head, tail, dropped), daemon=True)
    reader.start()
    timed_out = False
    try:
        returncode: int | None = process.wait(timeout=PROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        returncode, timed_out = None, True
    finally:
        reader.join(timeout=5)
        process.stdout.close()
    marker = f"\n[... {dropped[0]} bytes of output omitted ...]\n".encode() if dropped[0] else b""
    output = bytes(head + marker + tail).decode("utf-8", errors="replace")
    if returncode not in (0, None) and output.startswith("bwrap: "):
        raise SandboxUnavailable(f"sandbox failed during a test run (exit {returncode}): {output.strip()[:500]}")
    if timed_out:
        output += f"\n[test run stopped after {PROCESS_TIMEOUT_SECONDS}s]"
    # Agents see repository-relative paths only.
    return TestRun(returncode, output.replace(str(repo) + os.sep, "").replace(str(repo), "."), timed_out)
