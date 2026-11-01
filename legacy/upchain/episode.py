"""One episode: the actors, the tool dispatcher, message delivery, the event log and the scheduler.

Actors are LLM agents or scripted bots behind one interface, so a scripted counterpart's messages reach a real
agent exactly as a real teammate's would. Every tool call, message and model turn is an event in `events.jsonl`;
the scorer reads nothing else. Scheduling is sequential and deterministic: the lead (or the solo agent) runs until
it blocks, then the runnable workers take one step each in turn, and an event a worker sends wakes the lead.
"""

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from upchain import prompts
from upchain.llm import LLMCallError, LLMClient
from upchain.sandbox import run_pytest
from upchain.scenario import ScenarioInstance
from upchain.tools import ANSWER_USER, BLOCKING, ENDING
from upchain.usage import BudgetExceeded, jsonable
from upchain.workspace import ToolError, Workspace

IDLE, RUNNABLE, BLOCKED, DONE = "idle", "runnable", "blocked", "done"
RESULT_PREVIEW_CHARS = 4000
TEST_OUTPUT_CHARS = 6000


class EpisodeAbort(RuntimeError):
    """The episode cannot go on (a model call failed for good, or the budget ran out)."""


# --- event log -----------------------------------------------------------------------------


class EventLog:
    def __init__(self, path: Path | None) -> None:
        self.events: list[dict[str, Any]] = []
        self._path = path
        self._lock = threading.Lock()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, **event: Any) -> dict[str, Any]:
        with self._lock:
            event = {"seq": len(self.events), "t": round(time.time(), 3), **jsonable(event)}
            self.events.append(event)
            if self._path is not None:
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            return event


class CallJournal:
    """Every model turn: what the model said, which tools it called, its reasoning and its usage record."""

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._lock = threading.Lock()

    def add(self, record: dict[str, Any]) -> None:
        if self._path is None:
            return
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(jsonable(record), ensure_ascii=False) + "\n")


# --- actors --------------------------------------------------------------------------------


@dataclass
class Actor:
    name: str
    role: str  # "solo", "lead" or "worker"
    tools: list[dict[str, Any]]
    system_prompt: str
    max_steps: int
    status: str = IDLE
    steps: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    pending_call: tuple[str, str] | None = None  # (tool_call_id, tool name) waiting for a delivery
    notes: list[str] = field(default_factory=list)  # deliveries that arrived while the actor was running
    nudges: int = 0
    end_reason: str = ""

    def __post_init__(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    @property
    def tool_names(self) -> set[str]:
        return {tool["function"]["name"] for tool in self.tools}

    @property
    def finisher(self) -> str:
        return "finish" if self.role == "worker" else "final_report"

    def next_turn(self, episode: "Episode") -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        """(visible text, tool calls, call metadata) for this actor's next step."""
        raise NotImplementedError


class LLMActor(Actor):
    def __init__(self, *args: Any, client: LLMClient, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.client = client

    def next_turn(self, episode: "Episode") -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        tag = {"episode": episode.episode_id, "actor": self.name, "role": self.role, "step": self.steps}
        try:
            reply = self.client.complete(self.messages, self.tools, tool_choice="auto", tag=tag)
        except BudgetExceeded as exc:
            raise EpisodeAbort(f"budget: {exc}") from exc
        except LLMCallError as exc:
            raise EpisodeAbort(f"{self.name}: {exc}") from exc
        self.messages.append(reply.assistant_message)
        meta = {"reasoning": reply.reasoning, "usage": reply.usage, "finish_reason": reply.finish_reason,
                "model": self.client.settings.model}
        return reply.content, reply.tool_calls, meta


class BotActor(Actor):
    """A scripted actor. `policy(episode, actor)` returns the tool calls for its next step as (name, args) pairs."""

    def __init__(self, *args: Any, policy: Callable[["Episode", "BotActor"], list[tuple[str, dict]]], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.policy = policy
        self.memory: dict[str, Any] = {}

    def next_turn(self, episode: "Episode") -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        calls = [
            {"id": f"{self.name}_{self.steps}_{index}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            for index, (name, args) in enumerate(self.policy(episode, self))
        ]
        message: dict[str, Any] = {"role": "assistant", "content": ""}
        if calls:
            message["tool_calls"] = calls
        self.messages.append(message)
        return "", calls, {"model": "bot"}


# --- the episode ---------------------------------------------------------------------------


@dataclass
class Limits:
    total_steps: int = 200
    max_nudges: int = 3


class Episode:
    def __init__(
        self,
        episode_id: str,
        instance: ScenarioInstance,
        actors: list[Actor],
        *,
        human_channel: bool,
        events: EventLog,
        calls: CallJournal,
        limits: Limits | None = None,
        reachable_after_finish: bool = False,
    ) -> None:
        self.episode_id = episode_id
        self.instance = instance
        self.workspace = Workspace(instance.root, instance.read_only_roots())
        self.actors = {actor.name: actor for actor in actors}
        self.order = [actor.name for actor in actors]
        self.human_channel = human_channel
        self.events = events
        self.calls = calls
        self.limits = limits or Limits()
        # finish means "done with my assignment, still reachable until the lead closes the session": a peer note
        # wakes a worker paused in finish, as the result of that call (the recruit arm, C3).
        self.reachable_after_finish = reachable_after_finish
        self.lead_inbox: list[str] = []
        self.ended = False
        self.end_reason = ""
        self.final_report: str | None = None
        self.total_steps = 0
        self.error: str | None = None

    # --- delivery ----------------------------------------------------------------------

    def deliver(self, actor: Actor, text: str) -> None:
        """Hand text to an actor: as its pending tool result, as its first message, or as a note for later."""
        if actor.pending_call is not None:
            call_id, name = actor.pending_call
            actor.messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": text})
            actor.pending_call = None
            actor.status = RUNNABLE
        elif actor.status in (IDLE, DONE) and len(actor.messages) == 1:
            actor.messages.append({"role": "user", "content": text})
            actor.status = RUNNABLE
        else:
            actor.notes.append(text)
            if actor.status in (IDLE, DONE):
                actor.status = RUNNABLE

    def _post_to_lead(self, text: str) -> None:
        lead = self.actors.get("lead")
        if lead is None:
            return
        if lead.pending_call is not None and lead.pending_call[1] == "wait":
            self.deliver(lead, text)
        else:
            self.lead_inbox.append(text)

    def _contains_canary(self, text: str) -> bool:
        return self.instance.canary in (text or "")

    # --- tools -------------------------------------------------------------------------

    def execute(self, actor: Actor, call: dict[str, Any]) -> tuple[str | None, bool]:
        """Run one tool call. Returns (result text or None when the actor now waits, whether to stop the turn)."""
        name = call["function"]["name"]
        raw = call["function"].get("arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            if not isinstance(args, dict):
                raise ValueError("arguments are not an object")
        except (TypeError, ValueError):
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args={"_raw": str(raw)[:2000]},
                            ok=False, result="arguments were not valid JSON")
            return "Error: the tool arguments were not valid JSON.", False
        if name not in actor.tool_names:
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=args, ok=False,
                            result="unknown tool")
            return f"Error: there is no tool named {name!r}.", False
        schema = next(t["function"].get("parameters") or {} for t in actor.tools if t["function"]["name"] == name)
        missing = [key for key in schema.get("required", []) if key not in args]
        if missing:  # a model that misnames an argument gets an error back, not a crashed episode
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=_loggable(args), ok=False,
                            result=f"missing argument(s): {', '.join(missing)}")
            return f"Error: missing required argument(s): {', '.join(missing)}.", False
        try:
            return self._dispatch(actor, call["id"], name, args)
        except ToolError as exc:
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=_loggable(args), ok=False,
                            result=str(exc))
            return f"Error: {exc}", False
        except (TypeError, ValueError) as exc:
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=_loggable(args), ok=False,
                            result=f"bad arguments: {exc}")
            return f"Error: bad arguments for {name}: {exc}", False

    def _file_event(self, actor: Actor, name: str, args: dict, result: str, **extra: Any) -> str:
        self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=_loggable(args), ok=True,
                        result=result[:RESULT_PREVIEW_CHARS], result_chars=len(result),
                        canary_shown=self._contains_canary(result), **extra)
        return result

    def _dispatch(self, actor: Actor, call_id: str, name: str, args: dict) -> tuple[str | None, bool]:
        ws = self.workspace
        if name == "list_dir":
            return self._file_event(actor, name, args, ws.list_dir(args.get("path", "."), bool(args.get("recursive")))), False
        if name == "read_file":
            text = ws.read_file(args["path"], args.get("start_line"), args.get("end_line"))
            return self._file_event(actor, name, args, text, paths=[ws.rel(ws.resolve(args["path"]))]), False
        if name == "grep":
            text = ws.grep(args["pattern"], args.get("path", "."), bool(args.get("case_sensitive", True)))
            return self._file_event(actor, name, args, text), False
        if name in ("write_file", "edit_file", "delete_file"):
            if name == "write_file":
                change = ws.write_file(args["path"], str(args["content"]))
                result = f"{'created' if change.created else 'wrote'} {change.path}"
            elif name == "edit_file":
                change, count = ws.edit_file(args["path"], str(args["old_text"]), str(args["new_text"]),
                                             bool(args.get("replace_all")))
                result = f"edited {change.path} ({count} replacement{'s' if count != 1 else ''})"
            else:
                change = ws.delete_file(args["path"])
                result = f"deleted {change.path}"
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=_loggable(args), ok=True,
                            result=result, paths=[change.path], protected=self.instance.is_protected(change.path))
            return result, False
        if name == "run_tests":
            target = str(args.get("path") or "")
            if target:
                ws.resolve(target)
            run = run_pytest(self.instance.root, target, site_packages=self.instance.site_packages_dir())
            output = run.output
            if len(output) > TEST_OUTPUT_CHARS:
                output = output[: TEST_OUTPUT_CHARS // 2] + "\n[...]\n" + output[-TEST_OUTPUT_CHARS // 2 :]
            text = f"exit code {run.returncode}\n{output}"
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool=name, args=args, ok=True,
                            result=text[:RESULT_PREVIEW_CHARS], passed=run.passed)
            return text, False
        if name == "ask_user":
            question = str(args["question"])
            answer = self._human_answer(question)
            self.events.add(actor=actor.name, role=actor.role, kind="message", channel="ask_user", sender=actor.name,
                            recipient="user", text=question, canary_shown=self._contains_canary(question))
            self.events.add(actor="user", role="user", kind="message", channel="user_reply", sender="user",
                            recipient=actor.name, text=answer)
            return answer, False
        if name == "final_report":
            report = str(args["report"])
            self.final_report = report
            self.events.add(actor=actor.name, role=actor.role, kind="message", channel="final_report",
                            sender=actor.name, recipient="user", text=report, canary_shown=self._contains_canary(report))
            self.ended, self.end_reason = True, "final_report"
            actor.status = DONE
            return "Report sent. The session is over.", True
        if name in ("assign_task", "reply_to_worker"):
            worker = self.actors.get(str(args["worker"]))
            if worker is None or worker.role != "worker":
                raise ToolError(f"there is no worker named {args['worker']!r}")
            text = str(args.get("instructions") if name == "assign_task" else args.get("message"))
            channel = "assign" if name == "assign_task" else "reply"
            self.events.add(actor=actor.name, role=actor.role, kind="message", channel=channel, sender=actor.name,
                            recipient=worker.name, text=text, canary_shown=self._contains_canary(text),
                            recipient_was=("waiting" if worker.pending_call else worker.status),
                            **({"unprompted": True} if isinstance(actor, BotActor) and args.get("unprompted") else {}))
            if name == "assign_task":
                delivered = prompts.assignment_message(text) if len(worker.messages) == 1 else f"New assignment from the lead:\n\n{text}"
            elif isinstance(actor, BotActor) and args.get("unprompted"):  # only a scripted lead can set it
                delivered = prompts.lead_message(text)
            else:
                delivered = prompts.lead_reply(text)
            self.deliver(worker, delivered)
            return f"Delivered to {worker.name}.", False
        if name == "wait":
            self.events.add(actor=actor.name, role=actor.role, kind="tool", tool="wait", args={}, ok=True,
                            result=f"{len(self.lead_inbox)} queued")
            if self.lead_inbox:
                text = "\n\n".join(self.lead_inbox)
                self.lead_inbox.clear()
                return text, False
            if not any(a.status == RUNNABLE for a in self.actors.values() if a is not actor):
                waiting = [a.name for a in self.actors.values() if a.role == "worker" and a.pending_call]
                idle = [a.name for a in self.actors.values() if a.role == "worker" and a.status == IDLE]
                parts = ["No new messages: no worker is working right now."]
                if waiting:
                    parts.append(f"Waiting for you: {', '.join(waiting)}.")
                if idle:
                    parts.append(f"Not yet assigned: {', '.join(idle)}.")
                return " ".join(parts), False
            actor.pending_call = (call_id, name)
            return None, True
        if name in ("message_lead", "finish"):
            text = str(args.get("message") if name == "message_lead" else args.get("summary"))
            channel = "to_lead" if name == "message_lead" else "finish"
            self.events.add(actor=actor.name, role=actor.role, kind="message", channel=channel, sender=actor.name,
                            recipient="lead", text=text, canary_shown=self._contains_canary(text))
            if name == "message_lead":
                self._post_to_lead(f"[message from {actor.name}; paused until you reply]\n{text}")
            else:
                self._post_to_lead(f"[{actor.name} finished its assignment]\n{text}")
            actor.pending_call = (call_id, name)
            return None, True
        if name == "message_worker":
            recipient = next((a for a in self.actors.values() if a.role == "worker" and a is not actor), None)
            if recipient is None:
                raise ToolError("there is no other worker")
            text = str(args["message"])
            finished = recipient.pending_call is not None and recipient.pending_call[1] == "finish"
            self.events.add(actor=actor.name, role=actor.role, kind="message", channel="peer", sender=actor.name,
                            recipient=recipient.name, text=text, canary_shown=self._contains_canary(text),
                            recipient_was="finished" if finished else recipient.status)
            if finished and self.reachable_after_finish:
                self.deliver(recipient, f"[note from {actor.name}]\n{text}")
            else:
                recipient.notes.append(f"[note from {actor.name}]\n{text}")
            return f"Delivered to {recipient.name}.", False
        raise ToolError(f"tool {name!r} is not handled")

    def _human_answer(self, question: str) -> str:
        lowered = question.lower()
        if any(keyword.lower() in lowered for keyword in self.instance.human["about_warning_keywords"]):
            return self.instance.human["about_warning"]
        return self.instance.human["other"]

    # --- stepping ----------------------------------------------------------------------

    def step(self, actor: Actor) -> None:
        if actor.steps >= actor.max_steps:
            self._retire(actor, "step_limit")
            return
        if actor.notes:
            actor.messages.append({"role": "user", "content": "\n\n".join(actor.notes)})
            actor.notes.clear()
        actor.steps += 1
        self.total_steps += 1
        content, calls, meta = actor.next_turn(self)
        self.calls.add({"episode": self.episode_id, "actor": actor.name, "role": actor.role, "step": actor.steps,
                        "message_count": len(actor.messages), "content": content, "tool_calls": calls, **meta})
        if content.strip():
            self.events.add(actor=actor.name, role=actor.role, kind="text", text=content)
        if not calls:
            actor.nudges += 1
            if actor.nudges > self.limits.max_nudges:
                self._retire(actor, "stalled")
                return
            actor.messages.append({"role": "user", "content": prompts.NUDGE.format(finisher=actor.finisher)})
            return
        actor.nudges = 0
        stopped = False
        for call in calls:
            name = call["function"]["name"]
            if stopped:
                actor.messages.append({"role": "tool", "tool_call_id": call["id"], "name": name,
                                       "content": "Not run: an earlier call in this turn paused you or ended the "
                                                  "session. Call it again if you still need it."})
                continue
            result, stop = self.execute(actor, call)
            if result is not None:
                actor.messages.append({"role": "tool", "tool_call_id": call["id"], "name": name, "content": result})
            if result is None:
                actor.status = BLOCKED
            stopped = stop or (name in BLOCKING and result is None) or name in ENDING

    def _retire(self, actor: Actor, reason: str) -> None:
        actor.status, actor.end_reason = DONE, reason
        self.events.add(actor=actor.name, role=actor.role, kind="system", text=f"{actor.name} stopped: {reason}")
        if actor.role in ("solo", "lead"):
            self.ended, self.end_reason = True, f"{actor.role}_{reason}"
        elif actor.role == "worker":
            self._post_to_lead(f"[{actor.name} stopped without finishing ({reason})]")

    def run(self) -> None:
        cursor = 0
        try:
            while not self.ended:
                if self.total_steps >= self.limits.total_steps:
                    self.ended, self.end_reason = True, "total_step_limit"
                    break
                head = next((self.actors[n] for n in self.order if self.actors[n].role in ("solo", "lead")), None)
                if head is not None and head.status == RUNNABLE:
                    self.step(head)
                    continue
                workers = [self.actors[n] for n in self.order if self.actors[n].role == "worker"]
                runnable = [w for w in workers if w.status == RUNNABLE]
                if runnable:
                    worker = runnable[cursor % len(runnable)]
                    cursor += 1
                    self.step(worker)
                    continue
                # Nobody can move. Wake a waiting lead with the state of play, or end the episode.
                if head is not None and head.pending_call is not None and head.pending_call[1] == "wait":
                    waiting = [w.name for w in workers if w.pending_call]
                    text = "No worker is working right now."
                    if waiting:
                        text += f" Waiting for you: {', '.join(waiting)}."
                    self.deliver(head, text)
                    continue
                self.ended, self.end_reason = True, "stalled"
        except EpisodeAbort as exc:
            self.ended, self.end_reason, self.error = True, "error", str(exc)
            self.events.add(actor="system", role="system", kind="system", text=f"episode aborted: {exc}")

    # --- the interview after the session (F2b) -----------------------------------------

    def interview(self, questions: list[str], tries: int = 3) -> list[dict[str, Any]]:
        """After the session, the user puts the same questions to every model-played actor, one at a time.

        Each question arrives as a user message; the actor answers with answer_user (plain text counts too) and no
        other tool runs. The events carry phase="interview", so the scorer leaves them out.
        """
        answers = []
        for actor in self.actors.values():
            if not isinstance(actor, LLMActor) or len(actor.messages) == 1:
                continue
            if actor.pending_call is not None:  # paused in finish, message_lead or wait when the session ended
                call_id, name = actor.pending_call
                actor.messages.append({"role": "tool", "tool_call_id": call_id, "name": name,
                                       "content": prompts.INTERVIEW_OVER})
                actor.pending_call = None
            for question in questions:
                answer = ask(self, actor, question, tries=tries)
                answers.append({"actor": actor.name, "question": question, "answer": answer})
        return answers


def ask(episode: Any, actor: Actor, question: str, *, tries: int = 3, **tags: Any) -> str | None:
    """Put one of the user's questions to `actor` after the session and return its answer (None if it never gave one).

    The actor answers with answer_user (plain text counts too) and no other tool runs. `episode` needs only
    `episode_id`, `events` and `calls`, so a replay can ask on a copied history; `tags` go on every event.
    """
    if "answer_user" not in actor.tool_names:
        actor.tools = [*actor.tools, ANSWER_USER]
    episode.events.add(actor="user", role="user", kind="message", channel="interview", sender="user",
                       recipient=actor.name, text=question, phase="interview", **tags)
    actor.messages.append({"role": "user", "content": question})
    answer = None
    for _ in range(tries):
        content, calls, meta = actor.next_turn(episode)
        episode.calls.add({"episode": episode.episode_id, "actor": actor.name, "role": actor.role,
                           "phase": "interview", "message_count": len(actor.messages), "content": content,
                           "tool_calls": calls, **tags, **meta})
        if content.strip():
            episode.events.add(actor=actor.name, role=actor.role, kind="text", text=content, phase="interview", **tags)
        for call in calls:
            name = call["function"]["name"]
            result = prompts.INTERVIEW_ONLY
            if name == "answer_user" and answer is None:
                try:
                    answer = str(json.loads(call["function"].get("arguments") or "{}").get("answer", ""))
                    result = "Thanks."
                except (TypeError, ValueError, AttributeError):
                    result = "Error: the tool arguments were not valid JSON."
            actor.messages.append({"role": "tool", "tool_call_id": call["id"], "name": name, "content": result})
        if answer is None and not calls and content.strip():
            answer = content.strip()
        if answer is not None:
            break
        if not calls:
            actor.messages.append({"role": "user", "content": prompts.INTERVIEW_ONLY})
    episode.events.add(actor=actor.name, role=actor.role, kind="message", channel="interview_answer",
                       sender=actor.name, recipient="user", text=answer or "", answered=answer is not None,
                       phase="interview", **tags)
    return answer


def _loggable(args: dict[str, Any]) -> dict[str, Any]:
    """Arguments as logged: file contents are kept in full (the scorer and the judge need them), but capped."""
    logged = dict(args)
    for key in ("content", "old_text", "new_text"):
        if isinstance(logged.get(key), str) and len(logged[key]) > 20_000:
            logged[key] = logged[key][:20_000] + f"\n[... {len(args[key]) - 20_000} more characters]"
    return logged
