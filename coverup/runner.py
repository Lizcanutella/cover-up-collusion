"""Setting up an arm's actors, playing episodes, and writing each episode's folder.

An episode folder holds `repo/` (the repository as the agents left it), `events.jsonl` (every tool call and
message), `calls.jsonl` (every model turn, with reasoning), `usage.jsonl` (every API attempt), `run.json` (settings,
outcome, usage summary and each actor's full history) and `score.json`. The journals are written as the episode
goes, so a stopped run keeps what it paid for.
"""

import json
import random
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from coverup import bots, prompts, tools
from coverup.config import ARMS, Config
from coverup.episode import CallJournal, Episode, EventLog, Limits, LLMActor, BotActor, Actor
from coverup.llm import LLMClient, LLMSettings
from coverup.scenario import build, load_spec
from coverup.score import score_episode
from coverup.usage import PriceTable, Spend, UsageLog, summarize

MODEL_ALIASES = {
    "haiku": "openrouter/anthropic/claude-haiku-5.5",
    "luna": "openrouter/openai/gpt-6-luna",
    "gemini-flash": "openrouter/google/gemini-3.8-flash",
    "qwen": "openrouter/qwen/qwen3.8-27b",
    "deepseek": "openrouter/deepseek/deepseek-v4.1-flash",
    "glm": "openrouter/z-ai/glm-5.3",
    "glm-flash": "openrouter/z-ai/glm-5.3-flash",
    "mistral": "openrouter/mistralai/mistral-small-2603",
    "minimax": "openrouter/minimax/minimax-m3.1-flash",
    "mimo": "openrouter/xiaomi/mimo-v2.6-flash",
    "gemini-lite": "openrouter/google/gemini-3.1-flash-lite",
}
BOT = "bot"  # the model name for a dry run: every model-played role is played by a scripted bot


def resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name, name)


def model_slug(model: str) -> str:
    return "bots" if model == BOT else model.rstrip("/").split("/")[-1]


def arm_label(arm: str, condition: str) -> str:
    return f"{arm}-{condition}" if condition else arm


# The scenario whose scripted roles live in bots.py; another scenario brings its own (scenario.yaml `scripted:`).
VENDORED_SDK = "vendored_sdk"


def conditions(arm: str, scenario: str) -> tuple[str, ...]:
    """The conditions an arm takes on a scenario: none for solo and team; for the peer arm, the scenario's peer notes
    (scenario.yaml `scripted.peer_notes`, or bots.PEER_NOTES on vendored_sdk); for the lead arm, bots.LEAD_ARM_REPORTS
    (vendored_sdk only)."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; one of {', '.join(ARMS)}")
    if arm in ("solo", "team"):
        return ()
    scripted = load_spec(scenario).get("scripted") or {}
    if arm == "peer" and scripted.get("peer_notes"):
        return tuple(scripted["peer_notes"])
    if arm == "lead" and scenario != VENDORED_SDK:
        raise ValueError(f"the lead arm's scripted workers are written for {VENDORED_SDK} only, not {scenario}")
    if scenario != VENDORED_SDK:
        raise ValueError(f"the {arm} arm's scripted roles are written for {VENDORED_SDK}, and {scenario} has no "
                         "scripted peer notes")
    return tuple(bots.PEER_NOTES) if arm == "peer" else tuple(bots.LEAD_ARM_REPORTS)


def check_condition(arm: str, condition: str, scenario: str) -> str:
    allowed = conditions(arm, scenario)
    if allowed and condition not in allowed:
        raise ValueError(f"arm {arm!r} needs --condition, one of {', '.join(allowed)}")
    if not allowed and condition:
        raise ValueError(f"arm {arm!r} takes no condition")
    return condition


# --- actors --------------------------------------------------------------------------------


def _repo(config: Config) -> str:
    return load_spec(config.scenario).get("repo_name", "ledgerly")


def _solo(config: Config, client: LLMClient | None) -> Actor:
    kwargs = dict(name="agent", role="solo", tools=tools.solo_tools(human_channel=config.human_channel),
                  system_prompt=prompts.solo_prompt(human_channel=config.human_channel, repo=_repo(config)),
                  max_steps=config.limits.solo)
    return LLMActor(**kwargs, client=client) if client else BotActor(**kwargs, policy=bots.solo_bot)


def _lead(config: Config, client: LLMClient | None, policy=None) -> Actor:
    kwargs = dict(
        name="lead", role="lead",
        tools=tools.lead_tools(human_channel=config.human_channel, file_tools=config.lead_file_tools),
        system_prompt=prompts.lead_prompt(human_channel=config.human_channel, lead_tools=config.lead_file_tools,
                                          repo=_repo(config)),
        max_steps=config.limits.lead,
    )
    return LLMActor(**kwargs, client=client) if client else BotActor(**kwargs, policy=policy)


def _worker(name: str, config: Config, client: LLMClient | None, policy=None, system_prompt: str | None = None) -> Actor:
    kwargs = dict(name=name, role="worker", tools=tools.worker_tools(peer_channel=config.peer_channel),
                  system_prompt=system_prompt or prompts.worker_prompt(name, peer_channel=config.peer_channel,
                                                                       repo=_repo(config)),
                  max_steps=config.limits.worker)
    return LLMActor(**kwargs, client=client) if client else BotActor(**kwargs, policy=policy)


def build_actors(arm: str, condition: str, config: Config, client: LLMClient | None) -> list[Actor]:
    """The arm's actors; `client` None means a dry run, with bots in the model-played roles."""
    check_condition(arm, condition, config.scenario)
    if arm == "solo":
        return [_solo(config, client)]
    if arm == "team":
        if client is None:
            return [_lead(config, None, bots.peer_lead),
                    _worker("worker_1", config, None, bots.solution_worker),
                    _worker("worker_2", config, None, bots.solution_worker)]
        return [_lead(config, client), _worker("worker_1", config, client), _worker("worker_2", config, client)]
    if arm == "peer":
        config = replace(config, peer_channel=True)  # the arm is about what passes over the peer channel
        return [_lead(config, None, bots.peer_lead_for(condition)),
                _worker("worker_1", config, client, None if client else bots.solution_worker),
                _worker("worker_2", config, None, bots.covering_peer(condition))]
    # The lead arm: worker_2 reports its vendor/ edit after the fact; in two_workers_ask worker_1 asks too.
    asker = bots.asking_worker if condition.endswith("_two_workers_ask") else bots.solution_worker
    return [_lead(config, client, None if client else bots.peer_lead),
            _worker("worker_1", config, None, asker),
            _worker("worker_2", config, None, bots.after_the_fact_worker(condition))]


# --- one episode ---------------------------------------------------------------------------


def run_episode(*, arm: str, condition: str, model: str, seed: int, config: Config, out_dir: Path,
                spend: Spend, prices: PriceTable | None, score_tests: bool = True) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    episode_id = f"{arm_label(arm, condition)}/{model_slug(model)}/ep{seed}"
    instance = build(config.scenario, out_dir / "repo", seed=seed, knobs=config.knobs)
    task_text = instance.task_text
    usage = UsageLog(out_dir / "usage.jsonl", prices=prices, shared_spend=spend)
    client = None
    if model != BOT:
        settings = LLMSettings(model=model, temperature=config.llm.temperature,
                               max_output_tokens=config.llm.max_output_tokens,
                               reasoning_effort=config.llm.reasoning_effort, provider_order=config.llm.provider_order)
        client = LLMClient(settings, usage)
    actors = build_actors(arm, condition, config, client)
    episode = Episode(
        episode_id, instance, actors, human_channel=config.human_channel,
        events=EventLog(out_dir / "events.jsonl"), calls=CallJournal(out_dir / "calls.jsonl"),
        limits=Limits(total_steps=config.limits.total, max_nudges=config.limits.max_nudges),
    )
    head = actors[0]
    episode.events.add(actor="user", role="user", kind="message", channel="task", sender="user", recipient=head.name,
                       text=task_text)
    episode.deliver(head, prompts.task_message(task_text))
    started = time.time()
    crash = None
    try:
        episode.run()
    except Exception:  # noqa: BLE001 - a harness bug must still leave a record behind
        crash = traceback.format_exc()
        episode.ended, episode.end_reason, episode.error = True, "harness_error", crash
    elapsed = round(time.time() - started, 1)
    score = score_episode(episode.events.events, instance, arm=arm_label(arm, condition),
                          final_report=episode.final_report, end_reason=episode.end_reason, run_tests=score_tests)
    score.update(model=model, seed=seed, condition=condition, cost_usd=summarize(usage.records, by=None)["cost_usd"])
    record = {
        "episode_id": episode_id,
        "arm": arm,
        "condition": condition,
        "model": model,
        "seed": seed,
        "status": "failed" if episode.error else "completed",
        "end_reason": episode.end_reason,
        "error": episode.error,
        "elapsed_seconds": elapsed,
        "config": config.to_dict(),
        "client": client.describe() if client else {"model": BOT},
        "scenario": instance.to_dict(),
        "steps": {a.name: {"steps": a.steps, "status": a.status, "end_reason": a.end_reason} for a in actors},
        "task_message": task_text,
        "final_report": episode.final_report,
        "usage": usage.summary(),
        "histories": {a.name: a.messages for a in actors},
    }
    (out_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out_dir / "score.json").write_text(json.dumps(score, ensure_ascii=False, indent=1), encoding="utf-8")
    return score


# --- batches and the spend ledger ----------------------------------------------------------


def ledger_total(path: Path) -> float:
    if not path.is_file():
        return 0.0
    return round(sum(json.loads(line).get("cost_usd", 0.0) for line in path.read_text().splitlines() if line.strip()), 6)


def run_batch(*, arm: str, condition: str, model: str, seeds: list[int], config: Config, out: Path,
              max_cost_usd: float | None, parallel: int = 1, score_tests: bool = True,
              label: str = "") -> list[dict[str, Any]]:
    """Play `seeds` of one arm. `condition` may list several conditions, comma-separated: they then run interleaved,
    each seed's conditions in a seed-shuffled order, under one cost ceiling and one ledger entry."""
    conditions = [check_condition(arm, c.strip(), config.scenario) for c in condition.split(",")]
    model = resolve_model(model)
    paid = model != BOT
    ledger = Path(config.budget.ledger)
    if paid:
        if max_cost_usd is None:
            raise ValueError("a paid run needs --max-cost-usd")
        spent = ledger_total(ledger)
        if spent + max_cost_usd > config.budget.total_usd + 1e-9:
            raise ValueError(
                f"the ledger ({ledger}) already shows ${spent:.4f}; a ceiling of ${max_cost_usd:.2f} could take the "
                f"total past the budget of ${config.budget.total_usd:.2f} (config budget.total_usd)"
            )
    prices = PriceTable.load(config.prices) if Path(config.prices).is_file() else None
    spend = Spend(max_cost_usd if paid else None)
    jobs = []
    for seed in seeds:
        order = list(conditions)
        random.Random(seed).shuffle(order)
        jobs += [(cond, seed) for cond in order]
    lock = threading.Lock()
    scores: list[dict[str, Any]] = []

    def one(job: tuple[str, int]) -> None:
        cond, seed = job
        episode_dir = out / arm_label(arm, cond) / model_slug(model) / f"ep{seed}"
        if episode_dir.exists():
            if paid:
                # A paid episode is never overwritten; pick other seeds or another --out.
                print(f"  skip {episode_dir} (exists)", flush=True)
                return
            shutil.rmtree(episode_dir)
        score = run_episode(arm=arm, condition=cond, model=model, seed=seed, config=config, out_dir=episode_dir,
                            spend=spend, prices=prices, score_tests=score_tests)
        with lock:
            scores.append(score)
            print(f"  {arm_label(arm, cond)} {model_slug(model)} ep{seed}: {score['outcome']} "
                  f"(end: {score['end_reason']}, violation: {score['violation']}, ${score['cost_usd']:.4f}, "
                  f"spent so far ${spend.total:.4f})", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=max(parallel, 1)) as pool:
            list(pool.map(one, jobs))
    finally:
        if paid:
            by_condition = {c: round(sum(s.get("cost_usd") or 0 for s in scores if s["condition"] == c), 6)
                            for c in conditions}
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label,
                    "arm": arm_label(arm, "+".join(conditions)), "model": model, "seeds": seeds,
                    "episodes_scored": len(scores), "cost_usd": round(spend.total, 6),
                    **({"conditions": conditions, "cost_by_condition": by_condition} if len(conditions) > 1 else {}),
                    "unpriced_calls": spend.unpriced_calls, "config": asdict(config.knobs),
                }) + "\n")
    return scores
