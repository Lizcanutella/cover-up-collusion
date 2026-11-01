"""The agents' file tools, confined to one episode's repository.

Agents get no shell. Every read and write goes through these functions, so the event log records exactly which
files each agent saw and changed. Paths are repository-relative; anything that resolves outside the repository,
any symlink and anything under `.git/` is refused. A scenario can add read-only roots (S17's installed packages,
seen at an absolute path such as /opt/venv/lib/python3.12/site-packages): the read tools accept paths under them,
and the write tools refuse them.
"""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_READ_LINES = 400
MAX_GREP_MATCHES = 200
MAX_LIST_ENTRIES = 400
MAX_FILE_BYTES = 400_000


class ToolError(Exception):
    """A tool call the agent made incorrectly; its message goes back to the agent."""


@dataclass(frozen=True)
class FileChange:
    path: str
    created: bool
    deleted: bool = False


class Workspace:
    def __init__(self, root: Path, read_only: dict[str, Path] | None = None) -> None:
        self.root = Path(root).resolve()
        # Absolute path the agents use -> host directory; empty for every scenario before S17.
        self.read_only = {mount.rstrip("/"): Path(host).resolve() for mount, host in (read_only or {}).items()}

    # --- paths ---------------------------------------------------------------------------

    def rel(self, path: Path) -> str:
        resolved = path.resolve()
        for mount, host in self.read_only.items():
            if resolved == host or host in resolved.parents:
                inner = resolved.relative_to(host).as_posix()
                return mount if inner == "." else f"{mount}/{inner}"
        return resolved.relative_to(self.root).as_posix() or "."

    def _read_only_root(self, raw: str) -> tuple[str, Path] | None:
        text = str(raw or "").strip()
        for mount, host in self.read_only.items():
            if text == mount or text.startswith(mount + "/"):
                return mount, host
        return None

    def _resolve_read_only(self, raw: str, mount: str, host: Path, must_exist: bool) -> Path:
        rest = str(raw).strip()[len(mount):].strip("/")
        parts = PurePosixPath(rest).parts if rest else ()
        if ".." in parts:
            raise ToolError(f"path {raw!r} leaves {mount}")
        probe = host
        for part in parts:
            probe = probe / part
            if probe.is_symlink():
                raise ToolError(f"path {raw!r} goes through a symlink, which is not allowed")
        resolved = (host / rest).resolve() if rest else host
        if resolved != host and host not in resolved.parents:
            raise ToolError(f"path {raw!r} leaves {mount}")
        if must_exist and not resolved.exists():
            raise ToolError(f"no such file or directory: {raw}")
        return resolved

    def _refuse_read_only(self, raw: str) -> None:
        if self._read_only_root(raw) is not None:
            raise ToolError(f"{raw} is outside the repository; it can be read but not changed")

    def resolve(self, raw: str, *, must_exist: bool = True) -> Path:
        external = self._read_only_root(raw)
        if external is not None:
            return self._resolve_read_only(raw, *external, must_exist)
        text = str(raw or ".").strip()
        if text.startswith("/"):
            # Agents often write the repository root as "/"; read absolute paths as repository-relative.
            text = text.lstrip("/") or "."
        parts = PurePosixPath(text).parts
        if ".." in parts:
            raise ToolError(f"path {raw!r} leaves the repository")
        if parts and parts[0] == ".git":
            raise ToolError("the .git directory is not available through this tool")
        candidate = self.root / text
        # Refuse symlinks anywhere on the way, so no path can lead outside the repository.
        probe = self.root
        for part in PurePosixPath(text).parts:
            if part in (".", ""):
                continue
            probe = probe / part
            if probe.is_symlink():
                raise ToolError(f"path {raw!r} goes through a symlink, which is not allowed")
        resolved = candidate.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ToolError(f"path {raw!r} leaves the repository")
        if must_exist and not resolved.exists():
            raise ToolError(f"no such file or directory: {text}")
        return resolved

    # --- reading -------------------------------------------------------------------------

    def list_dir(self, path: str = ".", recursive: bool = False) -> str:
        directory = self.resolve(path)
        if not directory.is_dir():
            raise ToolError(f"not a directory: {path}")
        entries: list[str] = []
        walker = sorted(directory.rglob("*")) if recursive else sorted(directory.iterdir())
        for entry in walker:
            rel = self.rel(entry)
            if rel.split("/")[0] == ".git" or "__pycache__" in rel.split("/"):
                continue
            entries.append(rel + ("/" if entry.is_dir() else ""))
        if not entries:
            return f"{self.rel(directory)}/ is empty"
        shown = entries[:MAX_LIST_ENTRIES]
        more = f"\n[... {len(entries) - len(shown)} more entries]" if len(entries) > len(shown) else ""
        return "\n".join(shown) + more

    def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError(f"not a file: {path}")
        if target.stat().st_size > MAX_FILE_BYTES:
            raise ToolError(f"{path} is too large to read ({target.stat().st_size} bytes)")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(int(start_line or 1), 1)
        end = min(int(end_line or len(lines)), len(lines), start + MAX_READ_LINES - 1)
        if not lines:
            return f"{self.rel(target)} is empty"
        numbered = [f"{number:>5}  {lines[number - 1]}" for number in range(start, end + 1)]
        note = ""
        if end < len(lines):
            note = f"\n[showing lines {start}-{end} of {len(lines)}; pass start_line to read further]"
        return f"{self.rel(target)}\n" + "\n".join(numbered) + note

    def grep(self, pattern: str, path: str = ".", case_sensitive: bool = True) -> str:
        try:
            regex = re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)
        except re.error as exc:
            raise ToolError(f"invalid regular expression: {exc}") from exc
        # Agents often pass several paths at once ("ledgerly scripts"); search each of them.
        raw_paths = [path] if (self.root / str(path).lstrip("/")).exists() or self._read_only_root(path) \
            or " " not in str(path) else str(path).split()
        files: list[Path] = []
        for raw in raw_paths:
            base = self.resolve(raw)
            files += [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        matches: list[str] = []
        total = 0
        for file in files:
            rel = self.rel(file)
            if rel.split("/")[0] == ".git" or "__pycache__" in rel.split("/") or file.is_symlink():
                continue
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    total += 1
                    if len(matches) < MAX_GREP_MATCHES:
                        matches.append(f"{rel}:{number}: {line.strip()[:300]}")
        if not matches:
            return "no matches"
        more = f"\n[... {total - len(matches)} more matches]" if total > len(matches) else ""
        return "\n".join(matches) + more

    # --- writing -------------------------------------------------------------------------

    def write_file(self, path: str, content: str) -> FileChange:
        self._refuse_read_only(path)
        target = self.resolve(path, must_exist=False)
        if target.is_dir():
            raise ToolError(f"{path} is a directory")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ToolError("content is too large")
        created = not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return FileChange(self.rel(target), created)

    def edit_file(self, path: str, old_text: str, new_text: str, replace_all: bool = False) -> tuple[FileChange, int]:
        self._refuse_read_only(path)
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError(f"not a file: {path}")
        if not old_text:
            raise ToolError("old_text must not be empty")
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            raise ToolError(f"old_text was not found in {path}")
        if count > 1 and not replace_all:
            raise ToolError(f"old_text occurs {count} times in {path}; add context or pass replace_all=true")
        target.write_text(text.replace(old_text, new_text) if replace_all else text.replace(old_text, new_text, 1),
                          encoding="utf-8")
        return FileChange(self.rel(target), False), (count if replace_all else 1)

    def delete_file(self, path: str) -> FileChange:
        self._refuse_read_only(path)
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError(f"not a file: {path}")
        target.unlink()
        return FileChange(self.rel(target), False, deleted=True)
