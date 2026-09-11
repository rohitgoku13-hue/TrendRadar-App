"""Portable, artifact-only read model for the public TrendRadar product shell."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_REFERENCE_MARKERS = ("file://", "localhost", "\\", ":/")
_MARKET_STATES = ("US_CONFIRMED", "NON_US_CONFIRMED", "COUNTRY_UNKNOWN")


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value)).hexdigest()


def _has_forbidden_reference(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_has_forbidden_reference(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_forbidden_reference(item) for item in value)
    if not isinstance(value, str):
        return False
    text = value.casefold()
    return any(marker in text for marker in _FORBIDDEN_REFERENCE_MARKERS)


def _read_mapping(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Selected public product artifact is unavailable or malformed.") from error
    if not isinstance(value, Mapping) or _has_forbidden_reference(value):
        raise ValueError("Selected public product artifact is unavailable or malformed.")
    return value


def _require_identity(value: Mapping[str, Any], *, artifact_id: str, prefix: str) -> None:
    identity = {key: item for key, item in value.items() if key not in {"artifact_id", "content_hash", "generated_at"}}
    digest = _hash(identity)
    if value.get("artifact_id") != artifact_id or value.get("content_hash") != digest or artifact_id != f"{prefix}{digest}":
        raise ValueError("Selected public product artifact has invalid immutable identity.")


@dataclass(frozen=True, slots=True)
class PublicCreatorSignal:
    ordinal: int
    opportunity_state: str
    pattern_state: str
    supporting_video_count: int
    qualifying_video_count: int
    representation_count: int
    structural_families: tuple[str, ...]
    market_state: str

    @property
    def tier(self) -> str:
        if self.opportunity_state == "CANDIDATE":
            return "STRUCTURALLY_CONFIRMED_CREATOR_OPPORTUNITY"
        if self.opportunity_state == "NOT_CANDIDATE":
            return "STRUCTURALLY_ASSESSED_NOT_OPPORTUNITY"
        if self.opportunity_state == "UNAVAILABLE_NO_STRUCTURAL_REPRESENTATION_EVIDENCE" and self.representation_count == 0:
            return "REPEATED_PERFORMANCE_SIGNAL_NO_STRUCTURAL_REPRESENTATION"
        return "STRUCTURAL_EVALUATION_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PublicCrossCreatorSignal:
    family_label: str
    mechanism_summary: str
    independent_creator_count: int
    supporting_evidence_count: int
    qualifying_evidence_count: int


@dataclass(frozen=True, slots=True)
class PublicTrend:
    family_label: str
    mechanism_summary: str
    market_lane: str
    rank: int
    independent_creator_count: int


@dataclass(frozen=True, slots=True)
class PublicProductReadModel:
    last_updated: str
    partition_counts: tuple[tuple[str, int], ...]
    explicit_gap_count: int
    discovery_completeness: str
    search_appearances: int
    unique_video_count: int
    qualifying_video_count: int
    qualified_creator_count: int
    creator_history_sufficient_count: int
    creator_signals: tuple[PublicCreatorSignal, ...]
    market_counts: tuple[tuple[str, int], ...]
    semantic_state: str
    cross_creator_signals: tuple[PublicCrossCreatorSignal, ...]
    validated_trends: tuple[PublicTrend, ...]


class PublicProductReadModelLoader:
    """Load three explicit safe artifacts without provider, legacy, or filesystem fallback."""

    def load(self, *, factual_artifact_id: str, semantic_artifact_id: str, projection_artifact_id: str) -> PublicProductReadModel:
        factual = _read_mapping(_ROOT / "storage" / "analytics" / "free_factual_v1" / f"{factual_artifact_id}.json")
        semantic = _read_mapping(_ROOT / "storage" / "analytics" / "semantic_trend_pipeline" / f"{semantic_artifact_id}.json")
        projection = _read_mapping(_ROOT / "storage" / "deployment" / f"{projection_artifact_id}.json")
        _require_identity(factual, artifact_id=factual_artifact_id, prefix="free-factual-v1-")
        _require_identity(semantic, artifact_id=semantic_artifact_id, prefix="semantic-trend-pipeline-")
        _require_identity(projection, artifact_id=projection_artifact_id, prefix="trend-radar-deployment-run-")
        opportunities = factual.get("opportunities")
        market_counts = factual.get("market_counts")
        partition_counts = projection.get("partition_counts")
        signals = semantic.get("cross_creator_signals")
        trend_groups = (semantic.get("primary_us_trends"), semantic.get("global_trends"), semantic.get("market_unknown_trends"))
        if not all(isinstance(value, list) for value in (opportunities, market_counts, partition_counts, signals, *trend_groups)):
            raise ValueError("Selected public product artifact has invalid product fields.")
        if (
            projection.get("factual_artifact_id") != factual_artifact_id
            or projection.get("factual_content_hash") != factual.get("content_hash")
            or projection.get("semantic_artifact_id") != semantic_artifact_id
            or projection.get("semantic_content_hash") != semantic.get("content_hash")
            or projection.get("discovery_execution_id") != factual.get("discovery_execution_id")
            or projection.get("discovery_execution_id") != semantic.get("discovery_execution_id")
            or projection.get("source_terminal_sha256") != factual.get("source_terminal_sha256")
            or projection.get("creator_signal_count") != len(opportunities)
            or projection.get("semantic_state") != semantic.get("overall_state")
            or projection.get("cross_creator_signal_count") != len(signals)
            or projection.get("validated_trend_count") != sum(len(group) for group in trend_groups)
        ):
            raise ValueError("Deployment projection does not match the selected public product sources.")
        parsed_partition_counts = tuple((str(key), int(count)) for key, count in partition_counts)
        parsed_market_counts = tuple((str(key), int(count)) for key, count in market_counts)
        if parsed_partition_counts != tuple(sorted(parsed_partition_counts)) or parsed_market_counts != tuple((state, dict(parsed_market_counts).get(state, 0)) for state in _MARKET_STATES):
            raise ValueError("Deployment projection product counts are invalid.")
        creators = tuple(PublicCreatorSignal(index, str(item["opportunity_state"]), str(item["pattern_state"]), int(item["supporting_video_count"]), int(item["qualifying_video_count"]), int(item["representation_count"]), tuple(str(value) for value in item["structural_families"]), str(item["market_state"])) for index, item in enumerate(opportunities, start=1) if isinstance(item, Mapping))
        signals_model = tuple(PublicCrossCreatorSignal(str(item["family_label"]), str(item["mechanism_summary"]), int(item["independent_creator_count"]), int(item["supporting_evidence_count"]), int(item["qualifying_evidence_count"])) for item in signals if isinstance(item, Mapping))
        trends = tuple(PublicTrend(str(item["family_label"]), str(item["mechanism_summary"]), str(item["market_lane"]), int(item["rank"]), int(item["independent_creator_count"])) for group in trend_groups for item in group if isinstance(item, Mapping))
        if len(creators) != len(opportunities) or any(item.market_state not in _MARKET_STATES for item in creators) or len(signals_model) != len(signals) or len(trends) != sum(len(group) for group in trend_groups):
            raise ValueError("Selected public product signals are invalid.")
        last_updated = semantic.get("generated_at")
        if not isinstance(last_updated, str) or not last_updated:
            raise ValueError("Selected public product artifact has no update timestamp.")
        factual_counts = {
            "search_appearances": factual.get("search_appearances"),
            "unique_video_count": factual.get("unique_video_count"),
            "qualifying_video_count": factual.get("qualifying_video_count"),
            "qualified_creator_count": factual.get("qualified_creator_count"),
            "creator_history_sufficient_count": factual.get("creator_history_sufficient_count"),
        }
        if (
            factual.get("discovery_completeness") != "COMPLETE"
            or any(not isinstance(value, int) or value < 0 for value in factual_counts.values())
            or factual_counts["qualified_creator_count"] != len(creators)
        ):
            raise ValueError("Selected public product artifact has invalid factual summary fields.")
        return PublicProductReadModel(
            last_updated=last_updated,
            partition_counts=parsed_partition_counts,
            explicit_gap_count=int(projection["explicit_gap_count"]),
            discovery_completeness=str(factual["discovery_completeness"]),
            search_appearances=int(factual_counts["search_appearances"]),
            unique_video_count=int(factual_counts["unique_video_count"]),
            qualifying_video_count=int(factual_counts["qualifying_video_count"]),
            qualified_creator_count=int(factual_counts["qualified_creator_count"]),
            creator_history_sufficient_count=int(factual_counts["creator_history_sufficient_count"]),
            creator_signals=creators,
            market_counts=parsed_market_counts,
            semantic_state=str(semantic["overall_state"]),
            cross_creator_signals=signals_model,
            validated_trends=trends,
        )
