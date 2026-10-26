"""The run configuration: a YAML file read into frozen dataclasses. Unknown keys are refused."""

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from coverup.scenario import Knobs

# solo: one agent; team: a model lead and two model workers; peer: the model is worker_1 and its teammates are
# scripted; lead: the model is the lead and its workers are scripted. The peer and lead arms' conditions come from the
# scenario (runner.conditions).
ARMS = ("solo", "team", "peer", "lead")


@dataclass(frozen=True)
class LLMConfig:
    temperature: float = 1.0
    max_output_tokens: int = 4096
    reasoning_effort: str = "default"
    provider_order: str = ""


@dataclass(frozen=True)
class StepLimits:
    solo: int = 60
    lead: int = 30
    worker: int = 40
    total: int = 160
    max_nudges: int = 3


@dataclass(frozen=True)
class Budget:
    ledger: str = "results/spend_ledger.jsonl"  # every paid run appends its cost here
    total_usd: float = 5.0  # no run starts if the ledger total plus its ceiling would pass this


@dataclass(frozen=True)
class Config:
    scenario: str = "vendored_sdk"
    knobs: Knobs = field(default_factory=Knobs)
    human_channel: bool = True
    peer_channel: bool = False
    lead_file_tools: tuple[str, ...] = ("list_dir",)
    limits: StepLimits = field(default_factory=StepLimits)
    llm: LLMConfig = field(default_factory=LLMConfig)
    budget: Budget = field(default_factory=Budget)
    prices: str = "configs/prices.yaml"

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def _build(cls: type, raw: dict[str, Any] | None, where: str) -> Any:
    raw = dict(raw or {})
    known = {f.name: f for f in fields(cls)}
    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise ValueError(f"unknown key(s) in {where}: {', '.join(unknown)}")
    nested = {"knobs": Knobs, "limits": StepLimits, "llm": LLMConfig, "budget": Budget}
    values = {}
    for key, value in raw.items():
        if key in nested and isinstance(value, dict):
            values[key] = _build(nested[key], value, f"{where}.{key}")
        elif key == "lead_file_tools":
            values[key] = tuple(value)
        else:
            values[key] = value
    return cls(**values)


def load(path: str | Path | None) -> Config:
    if path is None:
        return Config()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return _build(Config, raw, str(path))
