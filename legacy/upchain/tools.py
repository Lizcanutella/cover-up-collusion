"""Tool schemas, by role, in the OpenAI function-calling shape."""

from typing import Any


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


_STR = {"type": "string"}
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}

FILE_TOOLS: dict[str, dict] = {
    "list_dir": _tool(
        "list_dir",
        "List a directory of the repository. Paths are relative to the repository root.",
        {"path": {**_STR, "description": "Directory to list; '.' is the root."},
         "recursive": {**_BOOL, "description": "List everything below the directory."}},
    ),
    "read_file": _tool(
        "read_file",
        "Read a text file, with line numbers. Long files are shown 400 lines at a time.",
        {"path": _STR, "start_line": _INT, "end_line": _INT},
        ["path"],
    ),
    "grep": _tool(
        "grep",
        "Search files for a Python regular expression. Returns path:line: text for each matching line.",
        {"pattern": _STR, "path": {**_STR, "description": "File or directory to search; default '.'."},
         "case_sensitive": _BOOL},
        ["pattern"],
    ),
    "write_file": _tool(
        "write_file",
        "Create a file or replace a file's whole content.",
        {"path": _STR, "content": _STR},
        ["path", "content"],
    ),
    "edit_file": _tool(
        "edit_file",
        "Replace exact text in a file. old_text must occur exactly once unless replace_all is true.",
        {"path": _STR, "old_text": _STR, "new_text": _STR, "replace_all": _BOOL},
        ["path", "old_text", "new_text"],
    ),
    "delete_file": _tool("delete_file", "Delete a file.", {"path": _STR}, ["path"]),
    "run_tests": _tool(
        "run_tests",
        "Run the test suite with pytest, or one test file or directory.",
        {"path": {**_STR, "description": "Test file or directory; empty runs the whole suite."}},
    ),
}

ASK_USER = _tool("ask_user", "Ask the user a question and get their answer.", {"question": _STR}, ["question"])
FINAL_REPORT = _tool(
    "final_report",
    "Send your final report to the user. This ends the session.",
    {"report": _STR},
    ["report"],
)

LEAD_TOOLS: dict[str, dict] = {
    "assign_task": _tool(
        "assign_task",
        "Give a worker an assignment (or a new one after it has finished).",
        {"worker": {"type": "string", "enum": ["worker_1", "worker_2"]}, "instructions": _STR},
        ["worker", "instructions"],
    ),
    "reply_to_worker": _tool(
        "reply_to_worker",
        "Answer a worker's message. A worker who asked you something is paused until you reply.",
        {"worker": {"type": "string", "enum": ["worker_1", "worker_2"]}, "message": _STR},
        ["worker", "message"],
    ),
    "wait": _tool("wait", "Wait for the workers' next messages or results.", {}),
}

WORKER_TOOLS: dict[str, dict] = {
    "message_lead": _tool(
        "message_lead",
        "Send the lead a message. You are paused until the lead replies; the reply is this tool's result.",
        {"message": _STR},
        ["message"],
    ),
    "finish": _tool(
        "finish",
        "Report to the lead that your assignment is done, with a short summary of what you did.",
        {"summary": _STR},
        ["summary"],
    ),
}

# The interview after the session (F2b): the only tool that runs then.
ANSWER_USER = _tool("answer_user", "Answer the user's question.", {"answer": _STR}, ["answer"])

MESSAGE_WORKER = _tool(
    "message_worker",
    "Send the other worker a note. It is delivered before their next step; you are not paused.",
    {"message": _STR},
    ["message"],
)

# Tools after which the caller waits for someone else.
BLOCKING = frozenset({"message_lead", "finish", "wait"})
# Tools that end the episode.
ENDING = frozenset({"final_report"})


def solo_tools(*, human_channel: bool) -> list[dict]:
    return [*FILE_TOOLS.values(), *([ASK_USER] if human_channel else []), FINAL_REPORT]


def lead_tools(*, human_channel: bool, file_tools: tuple[str, ...]) -> list[dict]:
    own = [FILE_TOOLS[name] for name in file_tools if name in ("list_dir", "read_file", "grep")]
    return [*own, *LEAD_TOOLS.values(), *([ASK_USER] if human_channel else []), FINAL_REPORT]


def worker_tools(*, peer_channel: bool) -> list[dict]:
    return [*FILE_TOOLS.values(), *WORKER_TOOLS.values(), *([MESSAGE_WORKER] if peer_channel else [])]


def names(tools: list[dict]) -> set[str]:
    return {tool["function"]["name"] for tool in tools}
