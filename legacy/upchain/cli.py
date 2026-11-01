"""Command line: python -m upchain {build, simulate, run, reinterview, transcript, report, spend, show-prompt, cost}."""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

from upchain import prompts, tools
from upchain.config import ARMS, load
from upchain.runner import BOT, MODEL_ALIASES, arm_label, ledger_total, resolve_model, run_batch
from upchain.scenario import Knobs, build
from upchain.score import load_events

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    # This repository's .env first, then the shared one beside the sibling projects.
    for path in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


def _seeds(args: argparse.Namespace) -> list[int]:
    return list(range(args.seed_start, args.seed_start + args.n))


def cmd_build(args: argparse.Namespace) -> int:
    config = load(args.config)
    knobs = Knobs(warning=args.warning or config.knobs.warning, header=config.knobs.header, task=config.knobs.task)
    instance = build(config.scenario, Path(args.out), seed=args.seed, knobs=knobs)
    print(json.dumps({k: v for k, v in instance.to_dict().items() if k != "baseline"}, indent=1))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    config = load(args.config)
    run_batch(arm=args.arm, condition=args.condition, model=BOT, seeds=_seeds(args), config=config,
              out=Path(args.out), max_cost_usd=None, parallel=args.parallel)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    _load_env()
    if not os.environ.get("OPENROUTER_API_KEY") and resolve_model(args.model).startswith("openrouter/"):
        print("OPENROUTER_API_KEY is not set (looked in .env here and in ../.env)", file=sys.stderr)
        return 2
    config = load(args.config)
    run_batch(arm=args.arm, condition=args.condition, model=args.model, seeds=_seeds(args), config=config,
              out=Path(args.out), max_cost_usd=args.max_cost_usd, parallel=args.parallel, label=args.label)
    print(f"ledger total: ${ledger_total(Path(config.budget.ledger)):.4f} of ${config.budget.pilot_total_usd:.2f}")
    return 0


def cmd_reinterview(args: argparse.Namespace) -> int:
    from upchain.replay import run_reinterview

    _load_env()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set (looked in .env here and in ../.env)", file=sys.stderr)
        return 2
    config = load(args.config)
    levels = args.levels.split(",") if args.levels else list(prompts.LEAD_ASKS if args.mode == "lead" else
                                                             prompts.INTERVIEW_LEVELS)
    run_reinterview(source=Path(args.source), out=Path(args.out), levels=levels, config=config,
                    max_cost_usd=args.max_cost_usd, parallel=args.parallel, label=args.label, limit=args.limit,
                    mode=args.mode, cells=args.cells.split(",") if args.cells else None,
                    episodes=set(Path(args.episodes).read_text().split()) if args.episodes else None, prime=args.prime)
    print(f"ledger total: ${ledger_total(Path(config.budget.ledger)):.4f} of ${config.budget.pilot_total_usd:.2f}")
    return 0


def _short(text: str, limit: int) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + f" [... {len(text) - limit} more chars]"


def cmd_transcript(args: argparse.Namespace) -> int:
    events = load_events(Path(args.episode) / "events.jsonl")
    for e in events:
        who = e.get("actor", "?")
        if e["kind"] == "message":
            arrow = f"{e['sender']} -> {e['recipient']} [{e['channel']}]"
            print(f"\n#{e['seq']} {arrow}{'  (CANARY)' if e.get('canary_shown') else ''}\n{_short(e['text'], args.width * 8)}")
        elif e["kind"] == "text":
            print(f"\n#{e['seq']} {who} says:\n{_short(e['text'], args.width * 8)}")
        elif e["kind"] == "tool":
            shown = {k: (_short(v, 80) if isinstance(v, str) else v) for k, v in (e.get("args") or {}).items()}
            flags = []
            if e.get("canary_shown"):
                flags.append("CANARY SHOWN")
            if e.get("protected"):
                flags.append("PROTECTED PATH")
            if not e.get("ok", True):
                flags.append("ERROR")
            line = f"#{e['seq']} {who}: {e['tool']}({json.dumps(shown, ensure_ascii=False)})"
            print(line + (f"  [{', '.join(flags)}]" if flags else ""))
            if args.results and e.get("result"):
                print("    -> " + _short(e["result"], args.width).replace("\n", "\n       "))
        else:
            print(f"#{e['seq']} [{e['kind']}] {e.get('text', '')}")
    score_path = Path(args.episode) / "score.json"
    if score_path.is_file():
        score = json.loads(score_path.read_text())
        print(f"\noutcome: {score['outcome']}  violation: {score['violation']}  stages: {score['stages']}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for path in sorted(Path(args.results).rglob("score.json")):
        score = json.loads(path.read_text())
        groups[(score["arm"], score.get("model", "?"))].append(score)
    if not groups:
        print("no score.json files found")
        return 1
    header = ("arm", "model", "n", "wrote_any", "violation", "informed", "acted_first", "warning_edited", "exposed", "reported", "deferred",
              "asked_user", "final_mentions", "tests_pass", "coverage", "cost_usd")
    rows = []
    for (arm, model), scores in sorted(groups.items()):
        n = len(scores)

        def rate(key: str, scores=scores, n=n) -> str:
            return f"{sum(bool(s.get(key)) for s in scores)}/{n}"

        reported = [s["stages"]["s2_worker_reported"] for s in scores if s["stages"]["s2_worker_reported"] is not None]
        deferences = [s["deference"] for s in scores if s.get("deference")]
        rows.append((
            arm, model.split("/")[-1], str(n), rate("protected_write"), rate("violation"), rate("informed_violation"),
            rate("wrote_before_escalating"), rate("warning_file_changed"),
            rate("exposed"), f"{sum(reported)}/{len(reported)}" if reported else "-",
            f"{sum(d['wrote_protected_after_reply'] for d in deferences)}/{len(deferences)}" if deferences else "-",
            rate("asked_user_about_warning"),
            f"{sum(bool(s['final_report_mentions']) for s in scores)}/{n}",
            f"{sum(bool(s['task'].get('tests_pass')) for s in scores)}/{n}",
            f"{sum(s['task']['coverage_outside'] or 0 for s in scores) / n:.2f}",
            f"{sum(s.get('cost_usd') or 0 for s in scores):.4f}",
        ))
        outcomes = Counter(s["outcome"] for s in scores)
        rows.append(("", "  outcomes: " + ", ".join(f"{k} {v}" for k, v in outcomes.most_common()), *[""] * 14))
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    for row in [header, *rows]:
        print("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    return 0


def cmd_rescore(args: argparse.Namespace) -> int:
    """Recompute score.json from each episode's events and repository, after a scorer change."""
    from upchain.scenario import ScenarioInstance, load_spec
    from upchain.score import score_episode

    for run_path in sorted(Path(args.results).rglob("run.json")):
        record = json.loads(run_path.read_text())
        data = dict(record["scenario"])
        data["root"] = run_path.parent / "repo"
        data["knobs"] = Knobs(**data["knobs"])
        data.setdefault("alert_events", load_spec(data["scenario"]).get("alert_events", []))  # saved before it existed
        instance = ScenarioInstance(**data)
        old = json.loads((run_path.parent / "score.json").read_text()) if (run_path.parent / "score.json").is_file() else {}
        score = score_episode(load_events(run_path.parent / "events.jsonl"), instance,
                              arm=arm_label(record["arm"], record["condition"]), final_report=record["final_report"],
                              end_reason=record["end_reason"])
        score.update({key: old[key] for key in ("model", "seed", "condition", "cost_usd") if key in old})
        (run_path.parent / "score.json").write_text(json.dumps(score, ensure_ascii=False, indent=1))
        print(f"{run_path.parent}: {score['outcome']}")
    return 0


def cmd_spend(args: argparse.Namespace) -> int:
    config = load(args.config)
    ledger = Path(config.budget.ledger)
    if ledger.is_file():
        for line in ledger.read_text().splitlines():
            entry = json.loads(line)
            print(f"{entry['time']}  {entry['arm']:<16} {entry['model'].split('/')[-1]:<20} "
                  f"seeds {entry['seeds'][0]}-{entry['seeds'][-1]}  ${entry['cost_usd']:.4f}  {entry.get('label', '')}")
    print(f"total ${ledger_total(ledger):.4f} of ${config.budget.pilot_total_usd:.2f}")
    return 0


def cmd_show_prompt(args: argparse.Namespace) -> int:
    from upchain.scenario import load_spec

    config = load(args.config)
    repo = load_spec(config.scenario).get("repo_name", "ledgerly")
    if args.role == "solo":
        system, schema = prompts.solo_prompt(human_channel=config.human_channel, repo=repo), tools.solo_tools(
            human_channel=config.human_channel)
    elif args.role == "lead":
        system = prompts.lead_prompt(human_channel=config.human_channel, lead_tools=config.lead_file_tools, repo=repo)
        schema = tools.lead_tools(human_channel=config.human_channel, file_tools=config.lead_file_tools)
    else:
        system = prompts.worker_prompt(args.role, peer_channel=config.peer_channel, repo=repo)
        schema = tools.worker_tools(peer_channel=config.peer_channel)
    print(system)
    print("\ntools: " + ", ".join(sorted(tools.names(schema))))
    return 0


def cmd_cost(args: argparse.Namespace) -> int:
    """Mean cost per episode of earlier paid episodes, by arm and model, times n."""
    costs: dict[tuple[str, str], list[float]] = defaultdict(list)
    for path in Path(args.results).rglob("score.json"):
        score = json.loads(path.read_text())
        if score.get("model") != BOT and score.get("cost_usd") is not None:
            costs[(score["arm"], score["model"])].append(float(score["cost_usd"]))
    key = (arm_label(args.arm, args.condition), resolve_model(args.model))
    if key not in costs:
        print(f"no earlier paid episodes for {key[0]} on {key[1]}; run a single episode first to measure")
        return 1
    mean = sum(costs[key]) / len(costs[key])
    print(f"{key[0]} on {key[1]}: mean ${mean:.4f} per episode over {len(costs[key])} episode(s); "
          f"{args.n} episodes ~ ${mean * args.n:.2f} (max seen ${max(costs[key]):.4f})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upchain", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default="configs/pilot.yaml")

    p = sub.add_parser("build", help="build one episode repository to look at")
    common(p)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--warning", default="")
    p.set_defaults(func=cmd_build)

    for name, func in (("simulate", cmd_simulate), ("run", cmd_run)):
        p = sub.add_parser(name, help="dry run with bots (free)" if name == "simulate" else "paid run")
        common(p)
        p.add_argument("--arm", choices=ARMS, required=True)
        p.add_argument("--condition", default="", help="one condition, or several comma-separated to run interleaved")
        p.add_argument("--n", type=int, default=1)
        p.add_argument("--seed-start", type=int, default=0)
        p.add_argument("--parallel", type=int, default=1)
        p.add_argument("--out", default="results/sim" if name == "simulate" else "results/pilot")
        if name == "run":
            p.add_argument("--model", required=True, help=f"a LiteLLM model or one of {', '.join(MODEL_ALIASES)}")
            p.add_argument("--max-cost-usd", type=float, required=True)
            p.add_argument("--label", default="")
        p.set_defaults(func=func)

    p = sub.add_parser("reinterview", help="paid: ask finished episodes new questions, one per branch")
    common(p)
    p.add_argument("--from", dest="source", required=True,
                   help="a results folder of finished episodes (interviewed or not)")
    p.add_argument("--out", required=True)
    p.add_argument("--mode", choices=("user", "lead"), default="user",
                   help="user: the user asks after the session; lead: the lead asks the worker, replying to its finish")
    p.add_argument("--levels", default="", help="comma-separated; default all of prompts.INTERVIEW_LEVELS (user) or "
                   "prompts.LEAD_ASKS (lead)")
    p.add_argument("--cells", default="", help="only these arm labels, comma-separated (e.g. peer-note,peer-cover)")
    p.add_argument("--parallel", type=int, default=1)
    p.add_argument("--episodes", default="",
                   help="a file of episode ids, one per line (e.g. peer-cover/gpt-6-luna/ep3)")
    p.add_argument("--prime", action="store_true", help="user mode: send each session once before its branches, so "
                   "they read it from the provider's cache")
    p.add_argument("--limit", type=int, default=None, help="only the first N episodes (a smoke test)")
    p.add_argument("--max-cost-usd", type=float, required=True)
    p.add_argument("--label", default="")
    p.set_defaults(func=cmd_reinterview)

    p = sub.add_parser("transcript", help="print an episode's events")
    p.add_argument("episode")
    p.add_argument("--results", action="store_true", help="show tool results too")
    p.add_argument("--width", type=int, default=300)
    p.set_defaults(func=cmd_transcript)

    p = sub.add_parser("report", help="aggregate score.json files")
    p.add_argument("results")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("rescore", help="recompute score.json files from the logs")
    p.add_argument("results")
    p.set_defaults(func=cmd_rescore)

    p = sub.add_parser("spend", help="show the spend ledger")
    common(p)
    p.set_defaults(func=cmd_spend)

    p = sub.add_parser("show-prompt", help="print a role's system prompt and tool list")
    common(p)
    p.add_argument("--role", choices=("solo", "lead", "worker_1", "worker_2"), required=True)
    p.set_defaults(func=cmd_show_prompt)

    p = sub.add_parser("cost", help="estimate a batch from earlier episodes")
    p.add_argument("--results", default="results")
    p.add_argument("--arm", choices=ARMS, required=True)
    p.add_argument("--condition", default="")
    p.add_argument("--model", required=True)
    p.add_argument("--n", type=int, default=1)
    p.set_defaults(func=cmd_cost)

    args = parser.parse_args(argv)
    return args.func(args)
