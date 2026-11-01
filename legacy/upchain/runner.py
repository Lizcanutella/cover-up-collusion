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

from upchain import bots, bots_audit, prompts, tools
from upchain.config import CONDITIONS, Config
from upchain.episode import CallJournal, Episode, EpisodeAbort, EventLog, Limits, LLMActor, BotActor, Actor
from upchain.llm import LLMClient, LLMSettings
from upchain.scenario import build, load_spec, user_fills
from upchain.score import score_episode
from upchain.usage import PriceTable, Spend, UsageLog, summarize

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


def check_condition(arm: str, condition: str, scenario: str = "") -> str:
    """The peer arm on a scenario with its own peer notes (S17 on) takes that scenario's conditions."""
    scripted = (load_spec(scenario).get("scripted") or {}).get("peer_notes") if arm == "peer" and scenario else None
    allowed = tuple(scripted) if scripted else CONDITIONS[arm]
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


# Arms whose scripted roles are written for S1: their messages name vendor/payments_sdk/ and its files. The peer arm
# also runs on a scenario whose scenario.yaml has a `scripted:` block with peer notes (S17 on).
S1_ONLY_ARMS = ("defer", "soften", "handle", "peer", "recruit", "inherit")
# The audit-volume scenarios (S16, S16b) have their own scripted roles for two of them (upchain/bots_audit.py).
AUDIT_CONDITIONS = {"peer": tuple(bots_audit.PEER_NOTES), "handle": tuple(bots_audit.POST_REPORTS)}


def _audit_actors(arm: str, condition: str, config: Config, client: LLMClient | None) -> list[Actor]:
    if condition not in AUDIT_CONDITIONS.get(arm, ()):
        raise ValueError(f"on {config.scenario} the {arm} arm takes "
                         f"{' or '.join(AUDIT_CONDITIONS.get(arm, ())) or 'no condition'}; other scripted roles are "
                         "written for s1_structlog")
    if arm == "peer":
        config = replace(config, peer_channel=True)
        lead = bots.make_peer_lead(bots_audit.PEER_ASSIGNMENTS, final=bots_audit.PEER_FINAL)
        return [_lead(config, None, lead),
                _worker("worker_1", config, client, None if client else bots_audit.solution_worker),
                _worker("worker_2", config, None, bots_audit.covering_peer(condition))]
    return [_lead(config, client, None if client else bots.scripted_lead("stop")),
            _worker("worker_1", config, None, bots_audit.after_the_fact_worker(condition)),
            _worker("worker_2", config, None, bots_audit.solution_worker)]


def build_actors(arm: str, condition: str, config: Config, client: LLMClient | None) -> list[Actor]:
    """The arm's actors; `client` None means a dry run, with bots in the model-played roles."""
    scripted = (load_spec(config.scenario).get("scripted") or {}).get("peer_notes")
    if arm in S1_ONLY_ARMS and config.scenario != "s1_structlog" and not (arm == "peer" and scripted):
        if load_spec(config.scenario).get("metrics") == "log_volume" and arm in AUDIT_CONDITIONS:
            return _audit_actors(arm, condition, config, client)
        raise ValueError(f"the {arm} arm's scripted roles are written for s1_structlog, not {config.scenario}")
    if arm == "peer" and scripted and condition not in scripted:
        raise ValueError(f"{config.scenario} has no peer note for condition {condition!r}; it has {sorted(scripted)}")
    if arm in ("solo", "inherit"):  # inherit: a solo agent in a repository prepared by bots.prepare_inherit
        return [_solo(config, client)]
    if arm == "team":
        if client is None:
            return [_lead(config, None, bots.scripted_lead("stop")),
                    _worker("worker_1", config, None, bots.reporting_worker("full")),
                    _worker("worker_2", config, None, bots.solution_worker)]
        return [_lead(config, client), _worker("worker_1", config, client), _worker("worker_2", config, client)]
    if arm == "defer":
        return [_lead(config, None, bots.scripted_lead(condition)),
                _worker("worker_1", config, client, None if client else bots.reporting_worker("full")),
                _worker("worker_2", config, None, bots.solution_worker)]
    if arm == "soften":
        return [_lead(config, None, bots.scripted_lead("stop", assignments=bots.SOFTEN_ASSIGNMENTS[condition])),
                _worker("worker_1", config, client, None if client else bots.reporting_worker("full")),
                _worker("worker_2", config, None, bots.solution_worker)]
    if arm == "handle" and condition in bots.ASK_LEAD_REPORTS:  # workers ask the lead: worker_2 migrates vendor/
        asker = bots.asking_worker if condition.endswith("_two_ask") else bots.solution_worker
        return [_lead(config, client, None if client else bots.scripted_lead("stop")),
                _worker("worker_1", config, None, asker),
                _worker("worker_2", config, None, bots.reporting_worker(condition))]
    if arm == "handle":
        return [_lead(config, client, None if client else bots.scripted_lead("stop")),
                _worker("worker_1", config, None, bots.reporting_worker(condition, obey=config.handle_worker_obeys)),
                _worker("worker_2", config, None, bots.solution_worker)]
    if arm == "peer":
        config = replace(config, peer_channel=True)  # the arm is about what passes over the peer channel
        return [_lead(config, None, bots.peer_lead_for(condition)),
                _worker("worker_1", config, client, None if client else bots.reporting_worker("none")),
                _worker("worker_2", config, None, bots.covering_peer(condition))]
    if arm == "recruit":
        # C3: both workers are models and can message each other; worker_2 may carry a private objective.
        config = replace(config, peer_channel=True)
        insider = prompts.insider_prompt("worker_2", condition, "vendor/payments_sdk")
        return [_lead(config, None, bots.peer_lead),
                _worker("worker_1", config, client, None if client else bots.reporting_worker("none")),
                _worker("worker_2", config, client, None if client else bots.recruiting_peer, system_prompt=insider)]
    raise ValueError(f"unknown arm {arm!r}")


# --- one episode ---------------------------------------------------------------------------


def run_episode(*, arm: str, condition: str, model: str, seed: int, config: Config, out_dir: Path,
                spend: Spend, prices: PriceTable | None, score_tests: bool = True) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    episode_id = f"{arm_label(arm, condition)}/{model_slug(model)}/ep{seed}"
    instance = build(config.scenario, out_dir / "repo", seed=seed, knobs=config.knobs)
    task_text = bots.prepare_inherit(instance, condition) if arm == "inherit" else instance.task_text
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
        reachable_after_finish=arm == "recruit",
    )
    head = actors[0]
    episode.events.add(actor="user", role="user", kind="message", channel="task", sender="user", recipient=head.name,
                       text=task_text)
    episode.deliver(head, prompts.task_message(task_text))
    started = time.time()
    crash = None
    interview: list[dict[str, Any]] = []
    try:
        episode.run()
        if config.interview and episode.final_report is not None and not episode.error:
            try:
                interview = episode.interview(prompts.interview_questions(instance.protected_dir,
                                                                          instance.edit_question,
                                                                          topic=instance.topic))
            except EpisodeAbort as exc:
                episode.error = f"interview: {exc}"
                episode.events.add(actor="system", role="system", kind="system", text=f"interview aborted: {exc}",
                                   phase="interview")
    except Exception:  # noqa: BLE001 - a harness bug must still leave a record behind
        crash = traceback.format_exc()
        episode.ended, episode.end_reason, episode.error = True, "harness_error", crash
    elapsed = round(time.time() - started, 1)
    score = score_episode(episode.events.events, instance, arm=arm_label(arm, condition),
                          final_report=episode.final_report, end_reason=episode.end_reason, run_tests=score_tests)
    score.update(model=model, seed=seed, condition=condition, cost_usd=summarize(usage.records, by=None)["cost_usd"],
                 interview=interview)
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
        "interview": interview,
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
    user_fills(config.scenario)  # S19: refuse before anything is written or spent until the user's values are in
    model = resolve_model(model)
    paid = model != BOT
    ledger = Path(config.budget.ledger)
    if paid:
        if max_cost_usd is None:
            raise ValueError("a paid run needs --max-cost-usd")
        spent = ledger_total(ledger)
        if spent + max_cost_usd > config.budget.pilot_total_usd + 1e-9:
            raise ValueError(
                f"the ledger ({ledger}) already shows ${spent:.4f}; a ceiling of ${max_cost_usd:.2f} could take the "
                f"total past the pilot budget of ${config.budget.pilot_total_usd:.2f}"
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
