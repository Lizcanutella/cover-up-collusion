"""The user's questions after the session (`coverup reinterview`), each on its own copy of the session (branching).

Every episode saves each actor's full history in `run.json`. The whole history is used, and the call the actor was
paused in when the session ended (its finish, message_lead or wait) gets "The session is over.", so the session is
exactly as the actor saw it when it ended. Each question then goes to a fresh copy of that history, so no answer can
lean on another; the actor answers with answer_user (prompts.INTERVIEW_LEVELS, or the scenario's rating question).
The source episode is only read. The output folder `<out>/<arm>-<condition>/<model>/ep<seed>/` holds
`interview.json` (one row per actor and question), `events.jsonl`, `calls.jsonl` and `usage.jsonl`.
"""

import copy
import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from coverup import prompts
from coverup.config import Config, _build
from coverup.episode import CallJournal, EpisodeAbort, EventLog, LLMActor, ask
from coverup.llm import LLMCallError, LLMClient, LLMSettings
from coverup.runner import arm_label, build_actors, ledger_total, model_slug
from coverup.scenario import load_spec
from coverup.tools import ANSWER_USER
from coverup.usage import BudgetExceeded, PriceTable, Spend, UsageLog, summarize


def session_history(record: dict[str, Any], actor: str) -> list[dict[str, Any]]:
    """`actor`'s history as the session left it, with its pending calls closed (`closed_history`)."""
    return closed_history(record["histories"][actor])


def actor_tools(record: dict[str, Any], actor: str) -> tuple[str, list[dict[str, Any]], int]:
    """(role, tool schemas, step limit) the actor had in the session, rebuilt from the arm and the saved config."""
    config: Config = _build(Config, record["config"], "run.json config")
    for built in build_actors(record["arm"], record["condition"], config, client=None):
        if built.name == actor:
            return built.role, built.tools, built.max_steps
    raise ValueError(f"{record['episode_id']}: the {record['arm']} arm has no actor {actor!r}")


def closed_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A saved history whose last turn ended in tool calls (the finish or message_lead the actor was paused in when
    the session ended), with each of those calls answered "The session is over."."""
    last = history[-1]
    if last.get("role") != "assistant" or not last.get("tool_calls"):
        return list(history)
    return [*history, *({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"],
                         "content": prompts.INTERVIEW_OVER} for call in last["tool_calls"])]


_PLAYED = object()  # stands in for a client, so build_actors builds the model-played roles as LLMActors


def askable(record: dict[str, Any]) -> list[str]:
    """The actors to question: every model-played actor that took a turn."""
    config: Config = _build(Config, record["config"], "run.json config")
    played = [actor.name for actor in build_actors(record["arm"], record["condition"], config, client=_PLAYED)
              if isinstance(actor, LLMActor)]
    return [name for name in played if len(record["histories"].get(name, [])) > 1]


PRIME_TOKENS = 16  # the priming call's output limit; its answer is thrown away


def prime_cache(context: Any, client: LLMClient, history: list[dict[str, Any]], tools: list[dict[str, Any]],
                **tags: Any) -> None:
    """Send the shared session once, with a tiny output limit, before its branches.

    The provider caches a request's whole prompt, and a later request reads that cache only if it begins with all of
    it. A branch is the session plus its own question, so without this no branch starts with an earlier branch's
    prompt and every one pays the full input price. The answer is thrown away; reaching the output limit before any
    text (truncated) is the expected outcome.
    """
    finish = ""
    try:
        reply = client.complete(copy.deepcopy(history), tools, tool_choice="auto",
                                tag={"episode": context.episode_id, "phase": "prime", **tags})
        finish = reply.finish_reason or ""
    except LLMCallError as exc:
        if exc.category != "truncated":
            raise EpisodeAbort(f"prime: {exc}") from exc
        finish = "length"
    except BudgetExceeded as exc:
        raise EpisodeAbort(f"budget: {exc}") from exc
    context.calls.add({"episode": context.episode_id, "phase": "prime", "message_count": len(history),
                       "finish_reason": finish, **tags})


def _rating_question(record: dict[str, Any]) -> str:
    """The scenario's `rating_question`, read from scenario.yaml as it is now, so sessions run before the question
    existed can be asked it; "" if it has none."""
    name = record["scenario"].get("scenario")
    return (load_spec(name).get("rating_question") or "").strip() if name else ""


def reinterview_episode(record: dict[str, Any], levels: list[str], out_dir: Path, *, spend: Spend,
                        prices: PriceTable | None, prime: bool = False,
                        completion: Callable[..., Any] | None = None) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=False)
    usage = UsageLog(out_dir / "usage.jsonl", prices=prices, shared_spend=spend)
    llm = record["config"]["llm"]
    settings = LLMSettings(model=record["model"], temperature=llm["temperature"],
                           max_output_tokens=llm["max_output_tokens"], reasoning_effort=llm["reasoning_effort"],
                           provider_order=llm["provider_order"])
    client = LLMClient(settings, usage, completion=completion)  # completion: a test's fake model
    prime_client = LLMClient(replace(settings, max_output_tokens=PRIME_TOKENS), usage, completion=completion)
    context = SimpleNamespace(episode_id=record["episode_id"], events=EventLog(out_dir / "events.jsonl"),
                              calls=CallJournal(out_dir / "calls.jsonl"))
    protected_dir = record["scenario"]["protected_dir"]
    edit_question = record["scenario"].get("edit_question", "")
    rating_question = _rating_question(record)
    rows = []
    error = ""
    for name in askable(record):
        role, tools, max_steps = actor_tools(record, name)
        history = session_history(record, name)
        if prime:  # the branches add answer_user, so the primed prompt must too
            answers = any(tool["function"]["name"] == "answer_user" for tool in tools)
            branch_tools = tools if answers else [*tools, ANSWER_USER]
            try:
                prime_cache(context, prime_client, history, branch_tools, actor=name, role=role)
            except EpisodeAbort as exc:
                error = str(exc)
                break
        for level in levels:  # one actor's branches in a row, so the provider can cache the shared history
            actor = LLMActor(name=name, role=role, tools=list(tools), system_prompt=history[0]["content"],
                             max_steps=max_steps, client=client)
            question = prompts.interview_level(level, protected_dir, edit_question, rating_question)
            actor.messages = copy.deepcopy(history)
            try:
                answer = ask(context, actor, question, level=level)
            except EpisodeAbort as exc:
                error = str(exc)
                break
            rows.append({"actor": name, "level": level, "question": question, "answer": answer})
        if error:
            break
    result = {"source": record["episode_id"], "arm": record["arm"], "condition": record["condition"],
              "model": record["model"], "seed": record["seed"], "levels": levels, "prime": prime, "error": error,
              "cost_usd": summarize(usage.records, by=None)["cost_usd"], "interview": rows}
    (out_dir / "interview.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def run_reinterview(*, source: Path, out: Path, levels: list[str], config: Config, max_cost_usd: float,
                    parallel: int = 1, label: str = "", limit: int | None = None, cells: list[str] | None = None,
                    episodes: set[str] | None = None, prime: bool = False,
                    completion: Callable[..., Any] | None = None) -> list[dict[str, Any]]:
    """Branch every finished episode under `source` once per level and actor (`askable`), under one ceiling and one
    ledger entry.

    `cells` keeps only those arm labels (e.g. "peer-excusable_no_request") and `episodes` only those episode ids (e.g.
    "peer-excusable_no_request/gpt-6-luna/ep3"). `prime` sends each actor's session once before its branches, so they
    read it from the provider's cache (`prime_cache`)."""
    known = [*prompts.INTERVIEW_LEVELS, prompts.RATE_LEVEL]
    unknown = [level for level in levels if level not in known]
    if unknown:
        raise ValueError(f"unknown level(s) {', '.join(unknown)}; one of {', '.join(known)}")
    ledger = Path(config.budget.ledger)
    spent = ledger_total(ledger)
    if spent + max_cost_usd > config.budget.total_usd + 1e-9:
        raise ValueError(f"the ledger ({ledger}) already shows ${spent:.4f}; a ceiling of ${max_cost_usd:.2f} could "
                         f"take the total past the budget of ${config.budget.total_usd:.2f} (config budget.total_usd)")
    records = []
    for path in sorted(source.glob("*/*/ep*/run.json"), key=lambda p: (str(p.parent.parent), int(p.parent.name[2:]))):
        record = json.loads(path.read_text(encoding="utf-8"))
        if cells is not None and arm_label(record["arm"], record["condition"]) not in cells:
            continue
        if episodes is not None and record["episode_id"] not in episodes:
            continue
        if askable(record) and not record.get("error"):
            records.append(record)
    records = records[:limit] if limit is not None else records
    if prompts.RATE_LEVEL in levels:  # refuse before anything is paid for
        missing = sorted({r["scenario"].get("scenario") or "?" for r in records if not _rating_question(r)})
        if missing:
            raise ValueError(f"the rate level needs a rating_question in scenario.yaml; missing for {', '.join(missing)}")
    prices = PriceTable.load(config.prices) if Path(config.prices).is_file() else None
    spend = Spend(max_cost_usd)
    lock = threading.Lock()
    results: list[dict[str, Any]] = []

    def one(record: dict[str, Any]) -> None:
        out_dir = out / arm_label(record["arm"], record["condition"]) / model_slug(record["model"]) / f"ep{record['seed']}"
        if out_dir.exists():  # paid answers are never overwritten
            print(f"  skip {out_dir} (exists)", flush=True)
            return
        rows = reinterview_episode(record, levels, out_dir, spend=spend, prices=prices, prime=prime,
                                   completion=completion)
        with lock:
            results.extend(rows)
            print(f"  {record['episode_id']}: {len(rows)} answer(s), spent so far ${spend.total:.4f}", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=max(parallel, 1)) as pool:
            list(pool.map(one, records))
    finally:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label, "arm": "reinterview",
                "model": records[0]["model"] if records else "", "seeds": sorted({r["seed"] for r in records}) or [0],
                "source": str(source), "cells": cells, "levels": levels, "prime": prime, "episodes": len(records),
                "answers": len(results),
                "cost_usd": round(spend.total, 6), "unpriced_calls": spend.unpriced_calls,
            }) + "\n")
    return results
