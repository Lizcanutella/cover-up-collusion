"""Per-call token accounting, run summaries and a spending ceiling.

`normalize_llm_usage` and `summarize` are adapted from joint-task-collusion's
`experiments/usage.py` (see THIRD_PARTY_LICENSES.md). `UsageLog`, `PriceTable` and `Spend` come from Referee
(`referee/usage.py`), which took the file from Countersign. It is copied here unchanged apart from this docstring.
"""

import json
import threading
from dataclasses import asdict, dataclass, is_dataclass
from math import isclose
from pathlib import Path
from typing import Any

import litellm
import yaml

TOKEN_FIELDS = (
    "input_tokens",
    "reasoning_tokens",
    "output_tokens",
    "provider_output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "uncached_input_tokens",
    "billable_output_tokens",
)
ACCEPTED = "accepted"
BLOCKED = "blocked"  # the provider refused the request; the attempt is not repeated
TRUNCATED = "truncated"  # the reply is empty because the model used every output token; the attempt is not repeated


class BudgetExceeded(RuntimeError):
    """The calls made so far cost more than the ceiling set for this invocation."""


@dataclass(frozen=True)
class ReportedUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    reasoning_tokens: int | None
    cached_input_tokens: int | None
    cache_write_input_tokens: int | None


def get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return jsonable(value.dict())
    return str(value)


def _first_int(mapping: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _nested_int(mapping: dict[str, Any], container_keys: tuple[str, ...], value_keys: tuple[str, ...]) -> int | None:
    for container_key in container_keys:
        container = mapping.get(container_key)
        if not isinstance(container, dict):
            continue
        value = _first_int(container, *value_keys)
        if value is not None:
            return value
    return None


def _reported_usage(raw_usage: dict[str, Any]) -> ReportedUsage:
    reasoning_tokens = _first_int(raw_usage, "reasoning_tokens", "thoughts_token_count", "thoughtsTokenCount")
    if reasoning_tokens is None:
        reasoning_tokens = _nested_int(
            raw_usage,
            ("completion_tokens_details", "output_tokens_details"),
            ("reasoning_tokens", "reasoningTokens"),
        )
    cached_input_tokens = _first_int(raw_usage, "cached_content_token_count", "cachedContentTokenCount")
    if cached_input_tokens is None:
        cached_input_tokens = _nested_int(
            raw_usage,
            ("prompt_tokens_details", "input_tokens_details"),
            ("cached_tokens", "cachedTokens"),
        )
    cache_write_input_tokens = _first_int(raw_usage, "cache_creation_input_tokens", "cacheWriteInputTokens")
    if cache_write_input_tokens is None:
        # OpenRouter says `cache_write_tokens`; LiteLLM's own detail object says `cache_creation_tokens`.
        cache_write_input_tokens = _nested_int(
            raw_usage,
            ("prompt_tokens_details", "input_tokens_details"),
            ("cache_write_tokens", "cacheWriteTokens", "cache_creation_tokens", "cacheCreationTokens"),
        )
    return ReportedUsage(
        input_tokens=_first_int(raw_usage, "prompt_tokens", "input_tokens", "prompt_token_count", "promptTokenCount"),
        output_tokens=_first_int(
            raw_usage, "completion_tokens", "output_tokens", "candidates_token_count", "candidatesTokenCount"
        ),
        total_tokens=_first_int(raw_usage, "total_tokens", "total_token_count", "totalTokenCount"),
        reasoning_tokens=reasoning_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
    )


def _output_token_breakdown(reported: ReportedUsage) -> tuple[int | None, int | None, str]:
    """Visible output tokens, reasoning tokens and where the reasoning count came from."""
    reasoning = reported.reasoning_tokens
    if reasoning is not None:
        if reported.output_tokens is None:
            return None, reasoning, "explicit"
        total_if_separate = None
        if reported.input_tokens is not None:
            total_if_separate = reported.input_tokens + reported.output_tokens + reasoning
        if reported.total_tokens is not None and reported.total_tokens == total_if_separate:
            return reported.output_tokens, reasoning, "explicit"
        # Most providers count reasoning inside the output tokens.
        return max(reported.output_tokens - reasoning, 0), reasoning, "explicit"
    if None in (reported.input_tokens, reported.output_tokens, reported.total_tokens):
        return reported.output_tokens, None, "unavailable"
    remainder = reported.total_tokens - reported.input_tokens - reported.output_tokens
    if remainder > 0:
        return reported.output_tokens, remainder, "inferred_from_total"
    return reported.output_tokens, None, "not_reported"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _price_from_cost_map(response: Any, requested_model: str) -> float | None:
    """Estimate list-rate cost using the response model, then the requested model."""
    for model in (None, requested_model):
        try:
            computed = litellm.completion_cost(
                completion_response=response,
                **({} if model is None else {"model": model}),
            )
        except Exception:  # noqa: BLE001, S112 - LiteLLM raises many kinds for an unlisted model; try the next name
            continue
        if _is_number(computed):
            return float(computed)
    return None


def _call_cost_usd(response: Any, requested_model: str) -> tuple[float | None, str]:
    """The call's cost and its source. An unpriced call stays None instead of counting as zero."""
    from_map = _price_from_cost_map(response, requested_model)
    hidden = get_attr(response, "_hidden_params", {})
    reported = None
    if isinstance(hidden, dict) and _is_number(hidden.get("response_cost")):
        reported = float(hidden["response_cost"])
    raw_cost = get_attr(get_attr(response, "usage", {}), "cost")  # OpenRouter returns the billed cost here
    if reported is None and _is_number(raw_cost):
        reported = float(raw_cost)
    if reported is None:
        return (None, "unavailable") if from_map is None else (from_map, "litellm_cost_map")
    if from_map is not None and isclose(reported, from_map, rel_tol=1e-9):
        return from_map, "litellm_cost_map"
    return reported, "endpoint_reported"


def normalize_llm_usage(response: Any, requested_model: str, *, call_failed: bool = False) -> dict[str, Any]:
    """Provider usage in one shape, with the original fields kept under `raw_usage`."""
    raw_usage = jsonable(get_attr(response, "usage", {}))
    if not isinstance(raw_usage, dict):
        raw_usage = {}
    reported = _reported_usage(raw_usage)
    output_tokens, reasoning_tokens, reasoning_source = _output_token_breakdown(reported)

    billable_output_tokens = None
    if reported.input_tokens is not None and reported.total_tokens is not None:
        billable_output_tokens = max(reported.total_tokens - reported.input_tokens, 0)
    elif reported.output_tokens is not None:
        billable_output_tokens = reported.output_tokens
    uncached_input_tokens = None
    if reported.input_tokens is not None:
        uncached_input_tokens = max(
            reported.input_tokens - (reported.cached_input_tokens or 0) - (reported.cache_write_input_tokens or 0),
            0,
        )
    no_tokens = reported.input_tokens is None and reported.output_tokens is None
    if no_tokens and call_failed:
        cost_usd, cost_source = 0.0, "no_tokens_billed"
    elif no_tokens:
        cost_usd, cost_source = None, "unavailable"
    else:
        cost_usd, cost_source = _call_cost_usd(response, requested_model)

    return {
        "requested_model": requested_model,
        "response_model": get_attr(response, "model", requested_model),
        "response_provider": get_attr(response, "provider", None),
        "input_tokens": reported.input_tokens,
        "reasoning_tokens": reasoning_tokens,
        "output_tokens": output_tokens,
        "provider_output_tokens": reported.output_tokens,
        "total_tokens": reported.total_tokens,
        "cached_input_tokens": reported.cached_input_tokens,
        "cache_write_input_tokens": reported.cache_write_input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "billable_output_tokens": billable_output_tokens,
        "reasoning_tokens_source": reasoning_source,
        "cost_usd": cost_usd,
        "cost_usd_source": cost_source,
        "raw_usage": raw_usage,
    }


def summarize(records: list[dict[str, Any]], by: str | None = "stage") -> dict[str, Any]:
    """Totals over call records, with an optional breakdown by one tag such as the stage."""
    summary: dict[str, Any] = {
        "call_count": len(records),
        "accepted_call_count": sum(record.get("response_status") == ACCEPTED for record in records),
    }
    for field_name in TOKEN_FIELDS:
        values = [record.get(field_name) for record in records]
        reported = [value for value in values if isinstance(value, int)]
        summary[field_name] = sum(reported)
        summary[f"{field_name}_missing_calls"] = len(values) - len(reported)
    prices = [record.get("cost_usd") for record in records]
    priced = [float(price) for price in prices if _is_number(price)]
    summary["cost_usd"] = round(sum(priced), 6)
    summary["cost_usd_missing_calls"] = len(prices) - len(priced)
    if by is not None:
        groups = sorted({str(record.get(by, "unknown")) for record in records})
        summary[f"by_{by}"] = {
            group: summarize([r for r in records if str(r.get(by, "unknown")) == group], by=None) for group in groups
        }
    return summary


@dataclass(frozen=True)
class PriceTable:
    """USD per million tokens by model, for estimates when the endpoint reports no cost."""

    prices: dict[str, tuple[float, float]]
    source: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "PriceTable":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        prices = {name: (float(row["input"]), float(row["output"])) for name, row in (raw.get("models") or {}).items()}
        return cls(prices, str(raw.get("source", "")))

    def lookup(self, model: str) -> tuple[float, float] | None:
        """Match the full model string, or its tail after a routing prefix such as `openrouter/`."""
        for name in (model, model.split("/", 1)[-1]):
            if name in self.prices:
                return self.prices[name]
        return None

    def cost(self, model: str, input_tokens: int, billable_output_tokens: int) -> float | None:
        price = self.lookup(model)
        if price is None:
            return None
        return (input_tokens * price[0] + billable_output_tokens * price[1]) / 1e6


class UsageLog:
    """Collects call records from several threads, journals them and enforces a spending ceiling.

    `shared_spend` lets several logs (one per run) count toward one ceiling.
    """

    def __init__(
        self,
        journal_path: Path | None = None,
        max_cost_usd: float | None = None,
        prices: PriceTable | None = None,
        shared_spend: "Spend | None" = None,
    ) -> None:
        self.records: list[dict[str, Any]] = []
        self._journal_path = journal_path
        self._prices = prices
        self._spend = shared_spend or Spend(max_cost_usd)
        self._lock = threading.Lock()
        if journal_path is not None:
            journal_path.parent.mkdir(parents=True, exist_ok=True)

    def check_budget(self) -> None:
        self._spend.check()

    def add(self, record: dict[str, Any]) -> dict[str, Any]:
        """Store one call record and return it as stored, with a table price if it had none."""
        record = jsonable(record)
        if record.get("cost_usd") is None and self._prices is not None and record.get("input_tokens") is not None:
            estimate = self._prices.cost(
                record.get("requested_model", ""), record["input_tokens"], record.get("billable_output_tokens") or 0
            )
            if estimate is not None:
                record["cost_usd"], record["cost_usd_source"] = estimate, "price_table"
        with self._lock:
            self.records.append(record)
            if self._journal_path is not None:
                with self._journal_path.open("a", encoding="utf-8") as journal:
                    journal.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._spend.add(record.get("cost_usd"), str(record.get("requested_model") or "unknown model"))
        return record

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return summarize(list(self.records))


class Spend:
    """A running total of dollars spent, shared between threads.

    Under a ceiling a call with no price (no endpoint cost, not in LiteLLM's map nor the price table) stops the
    invocation at the next check, since its cost cannot be counted. Without a ceiling it is only counted.
    """

    def __init__(self, max_cost_usd: float | None = None) -> None:
        self.max_cost_usd = max_cost_usd
        self.total = 0.0
        self.unpriced_calls = 0
        self.unpriced_model = ""  # the first model with an unpriced call
        self._lock = threading.Lock()

    def add(self, cost_usd: Any, model: str = "unknown model") -> None:
        with self._lock:
            if _is_number(cost_usd):
                self.total += float(cost_usd)
            else:
                self.unpriced_calls += 1
                self.unpriced_model = self.unpriced_model or model

    def check(self) -> None:
        """Raise before a new call when the ceiling is already passed, or a call under it had no price."""
        with self._lock:
            if self.max_cost_usd is None:
                return
            if self.total > self.max_cost_usd:
                raise BudgetExceeded(
                    f"spent ${self.total:.4f}, above the ceiling of ${self.max_cost_usd:.2f}; no further calls are made"
                )
            if self.unpriced_calls:
                raise BudgetExceeded(
                    f"a call to {self.unpriced_model} has no price, so the ceiling of ${self.max_cost_usd:.2f} "
                    "cannot be kept; add the model to the price table (configs/prices.yaml); no further calls are made"
                )
