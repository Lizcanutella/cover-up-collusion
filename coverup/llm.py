"""Model calls through LiteLLM with tool use: provider routing, retries, cache breakpoints and usage records.

Adapted from our earlier, unpublished client (routing, error classification, the retry loop and refusal handling) and
joint-task-collusion's `experiments/agents.py` and `experiments/llm.py` (tool-call normalisation, the prompt-cache
breakpoint and reasoning replay). See THIRD_PARTY_LICENSES.md. That client makes one plain completion per
decision; this one sends tool schemas, accepts a reply that is only tool calls, and returns the assistant message
to append to the agent's history, with any reasoning the provider needs to see again on the next turn.
"""

import itertools
import json
import os
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import litellm
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    ContentPolicyViolationError,
    ContextWindowExceededError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnsupportedParamsError,
)

from coverup.usage import ACCEPTED, BLOCKED, TRUNCATED, UsageLog, get_attr, jsonable, normalize_llm_usage

litellm.suppress_debug_info = True

REASONING_EFFORT_CHOICES = ("default", "none", "minimal", "low", "medium", "high", "xhigh")
# One OpenRouter endpoint per model, used when the config names no provider_order: providers of the same model
# differ up to 20x in price and from fp4 to bf16 in precision. Luna is only served by OpenAI.
PROVIDER_PINS = {
    "openrouter/deepseek/deepseek-v4.1-flash": "deepinfra/fp8",
    "openrouter/qwen/qwen3.8-27b": "deepinfra/bf16",
    "openrouter/z-ai/glm-5.3": "sail-research/fp8",
    # Each on its maker's own endpoint.
    "openrouter/mistralai/mistral-small-2603": "mistral",
    "openrouter/minimax/minimax-m3.1-flash": "minimax",
    "openrouter/xiaomi/mimo-v2.6-flash": "xiaomi/fp8",
    "openrouter/google/gemini-3.1-flash-lite": "google-ai-studio",
}
MAX_RETRIES = 8
RETRY_BASE_WAIT_SECONDS = 5
RETRY_MAX_WAIT_SECONDS = 60
RETRY_MAX_TOTAL_WAIT_SECONDS = 10 * 60
NON_RETRYABLE_ERRORS = (
    AuthenticationError,
    BadRequestError,
    ContentPolicyViolationError,
    ContextWindowExceededError,
    NotFoundError,
    PermissionDeniedError,
    UnsupportedParamsError,
)
REACHABLE_DESPITE_ERRORS = (
    litellm.RateLimitError,
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
    litellm.Timeout,
)


class LLMCallError(RuntimeError):
    """A model call failed for good: a non-retryable error, a hard quota or too many retries."""

    def __init__(self, message: str, category: str = "") -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class LLMSettings:
    model: str
    temperature: float = 1.0
    max_output_tokens: int = 4096
    reasoning_effort: str = "default"
    provider_order: str = ""  # comma-separated OpenRouter providers; empty means any
    timeout_seconds: float = 300.0
    rate_limit_patience_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.reasoning_effort not in REASONING_EFFORT_CHOICES:
            raise ValueError(f"reasoning_effort must be one of {REASONING_EFFORT_CHOICES}; got {self.reasoning_effort!r}")


@dataclass(frozen=True)
class Reply:
    content: str
    tool_calls: list[dict[str, Any]]  # OpenAI shape: {"id", "type", "function": {"name", "arguments"}}
    assistant_message: dict[str, Any]  # what to append to the history, with any reasoning to replay
    reasoning: str | None
    usage: dict[str, Any]
    finish_reason: Any = None
    raw_extra: dict[str, Any] = field(default_factory=dict)


# --- routing -------------------------------------------------------------------------------


def resolve_provider(model: str) -> tuple[str, str]:
    """Split a LiteLLM model string the way LiteLLM itself will read it."""
    try:
        model_name, provider, _, _ = litellm.get_llm_provider(model=model)
    except Exception:  # noqa: BLE001 - LiteLLM raises many kinds for a model it cannot place
        prefix, _, remainder = model.partition("/")
        return (remainder or prefix), (prefix if remainder else "openai")
    return model_name, provider


def effective_api_base(model: str) -> str:
    """An environment-configured base URL (`<PROVIDER>_BASE_URL`, then `<PROVIDER>_API_BASE`), or ""."""
    provider = resolve_provider(model)[1].upper()
    for variable in (f"{provider}_BASE_URL", f"{provider}_API_BASE"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value.rstrip("/")
    return ""


def _params_the_provider_cannot_map(model_name: str, provider: str, params: list[str]) -> list[str]:
    if not params:
        return []
    try:
        supported = litellm.get_supported_openai_params(model=model_name, custom_llm_provider=provider) or []
    except Exception:  # noqa: BLE001 - as above
        supported = []
    return [param for param in params if param not in supported]


def openrouter_provider_routing(model: str, provider_order: str) -> dict[str, Any]:
    """OpenRouter's `provider` field, pinning calls to the named providers with no fallback."""
    order = [name.strip() for name in (provider_order or PROVIDER_PINS.get(model, "")).split(",") if name.strip()]
    if not order:
        return {}
    if resolve_provider(model)[1] != "openrouter":
        raise ValueError(f"A provider order applies only to openrouter/ models; got {model!r}.")
    return {"provider": {"order": order, "allow_fallbacks": False}}


def completion_kwargs(settings: LLMSettings) -> dict[str, Any]:
    """Reasoning and routing kwargs for `litellm.completion`. Credentials come from the environment."""
    model_name, provider = resolve_provider(settings.model)
    kwargs: dict[str, Any] = {}
    routing = openrouter_provider_routing(settings.model, settings.provider_order)
    if routing:
        kwargs["extra_body"] = routing
    requested: list[str] = ["tool_choice"]
    forced: list[str] = []
    effort = settings.reasoning_effort
    if effort != "default":
        if provider == "deepseek":
            effort_kwargs = {"thinking": {"type": "disabled"}} if effort == "none" else {"reasoning_effort": effort}
            kwargs.update(effort_kwargs)
            forced.extend(effort_kwargs)
        else:
            kwargs["reasoning_effort"] = effort
            requested.append("reasoning_effort")
    forced.extend(_params_the_provider_cannot_map(model_name, provider, requested))
    if forced:
        kwargs["allowed_openai_params"] = forced
    return kwargs


def get_litellm_version() -> str | None:
    try:
        return version("litellm")
    except PackageNotFoundError:
        return None


def endpoint_metadata(model: str) -> dict[str, str]:
    """Provider, model name and base URL, without credentials."""
    model_name, provider = resolve_provider(model)
    metadata = {"provider": provider, "model_name": model_name}
    api_base = effective_api_base(model)
    if api_base:
        metadata["api_base"] = api_base
    return metadata


def validate_model_route(settings: LLMSettings) -> None:
    """Probe a model with one small request before a run starts. Costs a few tokens."""
    try:
        litellm.completion(
            model=settings.model,
            messages=[{"role": "user", "content": "ping"}],
            temperature=settings.temperature,
            max_tokens=16 if settings.reasoning_effort in ("default", "none") else settings.max_output_tokens,
            timeout=settings.timeout_seconds,
            **{key: value for key, value in completion_kwargs(settings).items() if key != "allowed_openai_params"},
        )
    except REACHABLE_DESPITE_ERRORS:
        return
    except Exception as exc:
        raise ValueError(f"Model {settings.model!r} could not be called: {type(exc).__name__}: {exc}") from exc


# --- prompt caching and reasoning replay ---------------------------------------------------

# Roles on which a message-level cache breakpoint is accepted.
_CACHE_BREAKPOINT_ROLES = frozenset({"system", "user", "tool"})


def marks_prompt_cache_breakpoint(model: str) -> bool:
    """Anthropic models need an explicit breakpoint; OpenAI and Gemini cache prefixes on their own.

    LiteLLM moves a message-level `cache_control` into the content blocks that OpenRouter expects.
    """
    model_name, provider = resolve_provider(model)
    lowered = model_name.lower()
    if provider == "anthropic":
        return True
    if provider == "bedrock":
        return "anthropic." in lowered
    return provider == "openrouter" and lowered.startswith("anthropic/")


def with_prompt_cache_breakpoint(model: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add one cache breakpoint at the newest cacheable turn, on a copy so breakpoints never pile up in history."""
    if not messages or not marks_prompt_cache_breakpoint(model):
        return messages
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") in _CACHE_BREAKPOINT_ROLES:
            marked = dict(messages[index])
            marked["cache_control"] = {"type": "ephemeral"}
            return [*messages[:index], marked, *messages[index + 1 :]]
    return messages


# Fields a provider may need to see again on the next turn (Gemini thought signatures travel in OpenRouter's
# `reasoning_details`; Anthropic signed thinking in `thinking_blocks`; DeepSeek in `reasoning_content`).
_REPLAY_FIELDS = ("reasoning_details", "thinking_blocks", "reasoning_content")


def _replay_fields(message: Any) -> dict[str, Any]:
    replay: dict[str, Any] = {}
    provider_fields = get_attr(message, "provider_specific_fields") or {}
    for name in _REPLAY_FIELDS:
        value = get_attr(message, name)
        if value in (None, "", [], {}) and isinstance(provider_fields, dict):
            value = provider_fields.get(name)
        if value not in (None, "", [], {}):
            replay[name] = jsonable(value)
    return replay


def _reasoning_text(message: Any) -> str | None:
    """Reasoning the provider returned beside the answer, when it returns any."""
    for name in ("reasoning_content", "reasoning"):
        value = get_attr(message, name)
        if isinstance(value, str) and value.strip():
            return value
    blocks = get_attr(message, "thinking_blocks")
    if isinstance(blocks, list):
        text = "\n".join(str(get_attr(block, "thinking", "") or "") for block in blocks).strip()
        return text or None
    return None


def normalize_tool_calls(raw_calls: Any) -> list[dict[str, Any]]:
    """Tool calls in the OpenAI shape, keeping provider metadata such as Gemini thought signatures."""
    normalized: list[dict[str, Any]] = []
    for call in raw_calls or []:
        function = get_attr(call, "function", {})
        entry: dict[str, Any] = {
            "id": get_attr(call, "id", "") or f"call_{len(normalized)}",
            "type": get_attr(call, "type", "function") or "function",
            "function": {"name": get_attr(function, "name", "") or "", "arguments": get_attr(function, "arguments", "{}")},
        }
        function_fields = get_attr(function, "provider_specific_fields")
        if function_fields:
            entry["function"]["provider_specific_fields"] = jsonable(function_fields)
        for metadata_key in ("extra_content", "provider_specific_fields"):
            metadata = get_attr(call, metadata_key)
            if metadata:
                entry[metadata_key] = jsonable(metadata)
        if not isinstance(entry["function"]["arguments"], str):
            entry["function"]["arguments"] = json.dumps(jsonable(entry["function"]["arguments"]), ensure_ascii=False)
        normalized.append(entry)
    return normalized


# --- error classification ------------------------------------------------------------------


def _error_evidence(exc: Exception) -> str:
    """All provider error material retained by LiteLLM, as searchable text."""
    evidence = [str(exc)]
    for attribute in ("body", "detail", "provider_specific_fields"):
        value = get_attr(exc, attribute)
        if value not in (None, "", {}, []):
            evidence.append(json.dumps(jsonable(value), ensure_ascii=False))
    response = get_attr(exc, "response")
    if response is not None:
        try:
            body = response.json()
        except Exception:  # noqa: BLE001 - the body may not be JSON, or may not be there
            body = get_attr(response, "text", "")
        if body not in (None, "", {}, []):
            evidence.append(body if isinstance(body, str) else json.dumps(jsonable(body), ensure_ascii=False))
    return "\n".join(evidence)


def _retry_after_seconds(exc: Exception, evidence: str) -> float | None:
    """HTTP Retry-After and google.rpc RetryInfo delays named by a provider error."""
    candidates: list[float] = []
    for source in (get_attr(exc, "headers"), get_attr(get_attr(exc, "response"), "headers")):
        items = getattr(source, "items", None)
        if not callable(items):
            continue
        for key, value in list(items()):
            if str(key).lower() != "retry-after":
                continue
            try:
                candidates.append(max(float(value), 0.0))
            except (TypeError, ValueError):
                try:
                    retry_at = parsedate_to_datetime(str(value))
                except (TypeError, ValueError, OverflowError):
                    continue
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                candidates.append(max((retry_at - datetime.now(UTC)).total_seconds(), 0.0))
    for pattern in (
        r'["\']retryDelay["\']\s*:\s*["\']([0-9]+(?:\.[0-9]+)?)s["\']',
        r'["\']retry_delay["\']\s*:\s*["\']([0-9]+(?:\.[0-9]+)?)s["\']',
        r"\bretry\s+in\s+([0-9]+(?:\.[0-9]+)?)s\b",
    ):
        candidates.extend(float(match) for match in re.findall(pattern, evidence, re.IGNORECASE))
    return max(candidates) if candidates else None


def _is_rate_limit(exc: Exception, evidence: str) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if 429 in (get_attr(get_attr(exc, "response"), "status_code"), get_attr(exc, "status_code")):
        return True
    return bool(
        re.search(r'["\']?code["\']?\s*:\s*429\b', evidence, re.IGNORECASE)
        or re.search(r'["\']?status["\']?\s*:\s*["\']RESOURCE_EXHAUSTED["\']', evidence, re.IGNORECASE)
        or re.search(r"\b(?:rate_limit_exceeded|quota_exceeded|too many requests)\b", evidence, re.IGNORECASE)
    )


def _is_hard_quota(exc: Exception, evidence: str) -> bool:
    if str(get_attr(exc, "rate_limit_type", "")).lower() in {"budget", "max_iterations"}:
        return True
    hard_patterns = (
        r"\b(?:insufficient_quota|quota_exceeded)\b",
        r"\b(?:requests?|tokens?|images?)\s+per\s+day\b",
        r"\b(?:rpd|tpd|ipd)\b",
        r"\bdaily\s+(?:quota|limit)\b",
        r"per[_ -]?day(?:\b|per)",
        r"\b(?:weekly|monthly)\s+(?:quota|limit)\b",
        r"\bkey\s+limit\s+exceeded\b",
        r"\b(?:billing|payment)\s+(?:account\s+)?(?:is\s+)?(?:disabled|inactive|not active|not linked|required)\b",
        r'["\'](?:quotaValue|quota_value|limit)["\']\s*:\s*["\']?0(?:\.0+)?["\']?(?![0-9.])',
    )
    return any(re.search(pattern, evidence, re.IGNORECASE) for pattern in hard_patterns)


def _is_refusal(exc: Exception, evidence: str) -> bool:
    if get_attr(exc, "status_code") == 403:
        return True
    return bool(re.search(r'"code"\s*:\s*403\b|\bpermission[-_ ]denied\b', evidence, re.IGNORECASE))


NETWORK_FAILURE = re.compile(
    r"name resolution|name or service not known|nodename nor servname|getaddrinfo failed|network is unreachable"
    r"|connection reset by peer|connection refused|server disconnected without sending a response",
    re.IGNORECASE,
)


def classify_error(exc: Exception) -> tuple[str, bool, float | None]:
    """(category, retryable, seconds the provider asked to wait)."""
    evidence = _error_evidence(exc)
    if isinstance(exc, ContentPolicyViolationError):
        return "content_policy", False, None
    if _is_rate_limit(exc, evidence):
        wait = _retry_after_seconds(exc, evidence)
        return ("hard_quota", False, wait) if _is_hard_quota(exc, evidence) else ("rate_limit", True, wait)
    if _is_refusal(exc, evidence):
        return "refused", False, None
    if isinstance(exc, NON_RETRYABLE_ERRORS):
        return "invalid_request", False, None
    if get_attr(exc, "status_code") == 402 or _is_hard_quota(exc, evidence):
        return "hard_quota", False, None
    if NETWORK_FAILURE.search(evidence):
        return "network", True, None
    return "transient", True, _retry_after_seconds(exc, evidence)


def _wait_seconds(retry_index: int, retry_after: float | None) -> float:
    backoff = min(RETRY_BASE_WAIT_SECONDS * (2**retry_index), RETRY_MAX_WAIT_SECONDS)
    return max(backoff, retry_after or 0.0) + random.uniform(0.0, min(1.0, backoff * 0.1))


BLOCKING_FINISH_REASONS = ("content_filter", "refusal")


def _block_notice(choice: Any, message: Any) -> str | None:
    """The provider's own words when it refused the request, or None when the answer is only empty."""
    fields = get_attr(message, "provider_specific_fields")
    refusal = get_attr(message, "refusal") or (fields.get("refusal") if isinstance(fields, dict) else None)
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()
    native = get_attr(choice, "provider_specific_fields")
    if isinstance(native, dict) and native.get("native_finish_reason") == "refusal":
        return "the provider gave no reason"
    if str(get_attr(choice, "finish_reason") or "").lower() in BLOCKING_FINISH_REASONS:
        return "the provider gave no reason"
    return None


# --- the client ----------------------------------------------------------------------------


class LLMClient:
    """One model behind `complete(messages, tools, tag)`, with retries and a usage record per attempt."""

    def __init__(
        self,
        settings: LLMSettings,
        usage: UsageLog | None = None,
        *,
        completion: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.usage = usage or UsageLog()
        self._completion = completion  # None means `litellm.completion`, looked up at each call
        self._sleep = sleep
        self._kwargs = completion_kwargs(settings)

    def describe(self) -> dict[str, Any]:
        return {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_output_tokens": self.settings.max_output_tokens,
            "reasoning_effort": self.settings.reasoning_effort,
            "provider_order": self.settings.provider_order,
            "litellm": get_litellm_version(),
            **endpoint_metadata(self.settings.model),
        }

    def _record(self, usage: dict[str, Any], tag: dict[str, Any], attempt: int, status: str, **extra: Any) -> dict:
        return self.usage.add({**tag, **usage, "api_attempt": attempt, "response_status": status, **extra})

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        tool_choice: str = "auto",
        tag: dict[str, Any] | None = None,
    ) -> Reply:
        """Return the model's next turn, retrying transient failures and empty answers.

        A turn with visible text or at least one tool call is accepted. A request the provider refuses is not
        retried: the call fails with the provider's notice.
        """
        tag = dict(tag or {})
        model = self.settings.model
        waited = 0.0
        patience = self.settings.rate_limit_patience_seconds
        spared = 0
        request: dict[str, Any] = dict(self._kwargs)
        if tools:
            request["tools"] = tools
            request["tool_choice"] = tool_choice
        else:
            request.pop("allowed_openai_params", None)
        for retry_index in itertools.count():
            self.usage.check_budget()
            try:
                response = (self._completion or litellm.completion)(
                    model=model,
                    # LiteLLM may mutate the request, and the breakpoint must not stay in the stored history.
                    messages=with_prompt_cache_breakpoint(model, [dict(message) for message in messages]),
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_output_tokens,
                    timeout=self.settings.timeout_seconds,
                    **request,
                )
            except Exception as exc:
                category, retryable, retry_after = classify_error(exc)
                usage = normalize_llm_usage(get_attr(exc, "response"), model, call_failed=True)
                self._record(
                    usage, tag, retry_index + 1, f"error_{category}", error_type=type(exc).__name__,
                    error_message=str(exc)[:2000],
                )
                if not retryable:
                    raise LLMCallError(f"{model}: {category}: {type(exc).__name__}: {exc}", category) from exc
                reason = f"{category}: {type(exc).__name__}"
                wait = _wait_seconds(retry_index, retry_after)
                if category in ("rate_limit", "network") and wait <= patience:
                    patience -= wait
                    spared += 1
                    self._sleep(wait)
                    continue
            else:
                choices = get_attr(response, "choices", []) or []
                choice = choices[0] if choices else None
                message = get_attr(choice, "message") if choice is not None else None
                content = (get_attr(message, "content", "") or "") if message is not None else ""
                tool_calls = normalize_tool_calls(get_attr(message, "tool_calls")) if message is not None else []
                usage = normalize_llm_usage(response, model)
                finish = jsonable(get_attr(choice, "finish_reason")) if choice is not None else None
                if content.strip() or tool_calls:
                    record = self._record(
                        usage, tag, retry_index + 1, ACCEPTED, finish_reason=finish, tool_call_count=len(tool_calls)
                    )
                    assistant: dict[str, Any] = {"role": "assistant", "content": content}
                    if tool_calls:
                        assistant["tool_calls"] = tool_calls
                    assistant.update(_replay_fields(message))
                    return Reply(
                        content=content,
                        tool_calls=tool_calls,
                        assistant_message=assistant,
                        reasoning=_reasoning_text(message),
                        usage=record,
                        finish_reason=finish,
                    )
                notice = _block_notice(choice, message)
                if notice is not None:
                    self._record(usage, tag, retry_index + 1, BLOCKED, finish_reason=finish, error_message=notice[:2000])
                    raise LLMCallError(f"{model}: blocked by the provider (finish reason {finish!r}): {notice}", "blocked")
                if str(finish).lower() == "length":
                    self._record(usage, tag, retry_index + 1, TRUNCATED, finish_reason=finish)
                    raise LLMCallError(
                        f"{model}: truncated: the model reached the output limit of {self.settings.max_output_tokens} "
                        "tokens before it produced any text or tool call",
                        "truncated",
                    )
                self._record(usage, tag, retry_index + 1, "empty", finish_reason=finish)
                reason = f"empty answer (finish reason {finish!r})"
                wait = _wait_seconds(retry_index, None)
            if retry_index - spared == MAX_RETRIES or waited + wait > RETRY_MAX_TOTAL_WAIT_SECONDS:
                raise LLMCallError(f"{model}: gave up after {retry_index + 1} attempts: {reason}", "gave_up")
            self._sleep(wait)
            waited += wait
        raise AssertionError("unreachable")
