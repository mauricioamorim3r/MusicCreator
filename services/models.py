from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def _serialize(value: Any) -> Any:
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            pass
    if is_dataclass(value):
        return {k: _serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value


@dataclass
class ResultEnvelope:
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)
    error: str | None = None
    mode: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass
class IngestResult(ResultEnvelope):
    """Result for uploaded or URL-based audio ingestion."""


@dataclass
class StemResult(ResultEnvelope):
    """Result for stem separation."""


@dataclass
class TranscriptResult(ResultEnvelope):
    """Result for lyric and prosody extraction."""


@dataclass
class MatchResult(ResultEnvelope):
    """Result for local mashup candidate matching."""


@dataclass
class AgentResults(ResultEnvelope):
    """Result for orchestrated LLM stages."""


@dataclass
class PipelineResult(ResultEnvelope):
    """Result for the end-to-end audio pipeline."""
