"""Consumer-safe read models and immutable snapshot loading for Trend Radar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from dashboard.product_read_model import PublicProductReadModel


IDENTITY_REFRESH_COPY = "Creator details will be available after the next refresh."
CONSUMER_SNAPSHOT_SCHEMA_VERSION = "consumer-trend-radar-v2"
_LEGACY_SNAPSHOT_SCHEMA_VERSION = "consumer-trend-radar-v1"
RETENTION_WINDOW_DAYS = 30
_SNAPSHOT_PREFIX = "consumer-trend-radar-candidate-"
_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_MARKERS = (
    "api_key", "authorization", "bearer ", "channel_id", "video_id",
    "gemini", "prompt_version", "methodology", "planner", "saturation",
    "provider_response", "request_audit", "filesystem", "c:\\", "d:\\", "\\\\",
)


@dataclass(frozen=True, slots=True)
class ConsumerVideo:
    """A public video card supplied directly by an authoritative consumer snapshot."""

    display_title: str
    views: int | None = None
    published_at: str | None = None
    thumbnail_locator: str | None = None
    public_video_locator: str | None = None
    creator_display_name: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumerCreator:
    """A public creator card with no requirement to expose an internal identity."""

    display_name: str | None
    public_handle: str | None = None
    public_creator_locator: str | None = None
    tracking_key: str | None = None
    subscriber_count: int | None = None
    breakout_video_count: int | None = None

    @property
    def safe_display_name(self) -> str:
        return self.display_name or IDENTITY_REFRESH_COPY


@dataclass(frozen=True, slots=True)
class ConsumerSubtrend:
    display_label: str
    videos: tuple[ConsumerVideo, ...]
    creators: tuple[ConsumerCreator, ...]
    summary: str | None = None
    status_label: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumerValidatedTrend:
    """A public Trend that is hard-bound to one backend-validated record."""

    trend_name: str
    description: str
    rank: int
    market_status: str
    evidence_summary: str
    videos: tuple[ConsumerVideo, ...]
    creators: tuple[ConsumerCreator, ...]
    provenance_digest: str

    def __post_init__(self) -> None:
        if (not self.trend_name or not self.description or self.rank < 1
                or len(self.provenance_digest) != 64
                or any(character not in "0123456789abcdef" for character in self.provenance_digest)):
            raise ValueError("Consumer validated Trend is malformed.")


@dataclass(frozen=True, slots=True)
class ConsumerTopic:
    topic_label: str
    subtrends: tuple[ConsumerSubtrend, ...]
    validated_trends: tuple[ConsumerValidatedTrend, ...] = ()
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumerCategory:
    category_label: str
    topics: tuple[ConsumerTopic, ...]
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class TrackCreatorCommand:
    """A future durable user-tracking request; it never implies local persistence."""

    tracking_key: str
    action: str

    def __post_init__(self) -> None:
        if self.action not in {"TRACK", "UNTRACK"}:
            raise ValueError("Consumer tracking action is invalid.")
        if not self.tracking_key:
            raise ValueError("Consumer tracking requires an opaque tracking key.")


@dataclass(frozen=True, slots=True)
class ConsumerTrendRadarV1:
    """The complete public snapshot used by the consumer hierarchy."""

    last_updated: str
    coverage_state: str
    categories: tuple[ConsumerCategory, ...]

    def __post_init__(self) -> None:
        if self.coverage_state not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Consumer snapshot coverage state is invalid.")
        if not self.last_updated:
            raise ValueError("Consumer snapshot requires an update timestamp.")
        labels = tuple(item.category_label for item in self.categories)
        if len(labels) != len(set(labels)):
            raise ValueError("Consumer snapshot contains duplicate category labels.")

    def category(self, label: str) -> ConsumerCategory | None:
        return next((item for item in self.categories if item.category_label == label), None)

    def topic(self, category_label: str, topic_label: str) -> ConsumerTopic | None:
        category = self.category(category_label)
        if category is None:
            return None
        return next((item for item in category.topics if item.topic_label == topic_label), None)

    def subtrend(self, category_label: str, topic_label: str, subtrend_label: str) -> ConsumerSubtrend | None:
        topic = self.topic(category_label, topic_label)
        if topic is None:
            return None
        return next((item for item in topic.subtrends if item.display_label == subtrend_label), None)

    def validated_trend(self, category_label: str, topic_label: str,
                        trend_name: str) -> ConsumerValidatedTrend | None:
        topic = self.topic(category_label, topic_label)
        if topic is None:
            return None
        return next((item for item in topic.validated_trends if item.trend_name == trend_name), None)


class ConsumerTrendRadarV1Projector:
    """Build the historical Sep 02 consumer projection without inventing records."""

    def project(self, source: PublicProductReadModel) -> ConsumerTrendRadarV1:
        coverage_state = "COMPLETE" if source.explicit_gap_count == 0 else "INCOMPLETE"
        return ConsumerTrendRadarV1(source.last_updated, coverage_state, ())


class ConsumerTrendRadarV1SnapshotLoader:
    """Load one exact immutable consumer candidate with retention-aware identities."""

    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder or _ROOT / "storage" / "deployment" / "consumer_snapshots"

    def load(self, *, snapshot_id: str, evaluation_time: datetime | None = None) -> ConsumerTrendRadarV1:
        if not snapshot_id.startswith(_SNAPSHOT_PREFIX):
            raise ValueError("Consumer snapshot identity is invalid.")
        path = self.folder / f"{snapshot_id}.json"
        try:
            raw = path.read_bytes()
            document = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Consumer snapshot is unavailable or malformed.") from error
        if not isinstance(document, Mapping):
            raise ValueError("Consumer snapshot is unavailable or malformed.")
        digest = snapshot_id.removeprefix(_SNAPSHOT_PREFIX)
        if len(digest) != 64 or sha256(raw).hexdigest() != digest:
            raise ValueError("Consumer snapshot immutable identity mismatch.")
        schema_version = document.get("schema_version")
        expected = {"schema_version", "generated_at", "window_start", "window_end", "coverage_state", "categories"}
        if schema_version == CONSUMER_SNAPSHOT_SCHEMA_VERSION:
            expected.add("api_data_expires_at")
        if set(document) != expected:
            raise ValueError("Consumer snapshot schema is malformed.")
        serialized = raw.decode("utf-8").casefold()
        if any(marker in serialized for marker in _FORBIDDEN_MARKERS):
            raise ValueError("Consumer snapshot contains prohibited private data.")
        if schema_version not in {CONSUMER_SNAPSHOT_SCHEMA_VERSION, _LEGACY_SNAPSHOT_SCHEMA_VERSION}:
            raise ValueError("Consumer snapshot schema version is unsupported.")
        if document.get("coverage_state") != "DISCOVERY_COVERAGE_COMPLETE":
            raise ValueError("Only complete consumer snapshots may be published.")
        now = evaluation_time or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("Consumer snapshot evaluation time must be timezone-aware.")
        categories = document.get("categories")
        if not isinstance(categories, list):
            raise ValueError("Consumer snapshot categories are malformed.")
        if schema_version == CONSUMER_SNAPSHOT_SCHEMA_VERSION:
            api_expires_at = _timestamp(_required_text(document, "api_data_expires_at"))
        else:
            api_expires_at = _timestamp(_required_text(document, "window_end")) + timedelta(days=RETENTION_WINDOW_DAYS)
        api_data_current = now.astimezone(UTC) < api_expires_at
        return ConsumerTrendRadarV1(
            _required_text(document, "generated_at"),
            "COMPLETE",
            tuple(_parse_category(item, now.astimezone(UTC), api_data_current) for item in categories),
        )


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError("Consumer snapshot field is malformed.")
    return item


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Consumer snapshot field is malformed.")
    return value


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Consumer snapshot record is malformed.")
    return value


def _records(value: Mapping[str, Any], key: str) -> list[object]:
    records = value.get(key)
    if not isinstance(records, list):
        raise ValueError("Consumer snapshot records are malformed.")
    return records


def _parse_category(value: object, now: datetime, api_data_current: bool) -> ConsumerCategory:
    record = _mapping(value)
    return ConsumerCategory(
        _required_text(record, "category_label"),
        tuple(_parse_topic(item, now, api_data_current) for item in _records(record, "topics")),
    )


def _parse_topic(value: object, now: datetime, api_data_current: bool) -> ConsumerTopic:
    record = _mapping(value)
    return ConsumerTopic(
        _required_text(record, "topic_label"),
        tuple(_parse_subtrend(item, now, api_data_current) for item in _records(record, "subtrends")),
        tuple(_parse_validated_trend(item, now, api_data_current)
              for item in record.get("validated_trends", [])),
    )


def _parse_subtrend(value: object, now: datetime, api_data_current: bool) -> ConsumerSubtrend:
    record = _mapping(value)
    return ConsumerSubtrend(
        _required_text(record, "subtrend_label"),
        tuple(_parse_video(item, api_data_current) for item in _records(record, "videos")),
        tuple(_parse_creator(item, now) for item in _records(record, "creators")),
    )


def _parse_video(value: object, api_data_current: bool) -> ConsumerVideo:
    record = _mapping(value)
    if not api_data_current:
        return ConsumerVideo("Video details unavailable pending refresh.")
    views = record.get("public_views")
    if not isinstance(views, int) or views < 0:
        raise ValueError("Consumer video views are malformed.")
    return ConsumerVideo(
        _required_text(record, "display_title"), views,
        _required_text(record, "published_at"), _optional_text(record.get("thumbnail_locator")),
        _required_text(record, "public_video_locator"),
    )


def _parse_validated_trend(value: object, now: datetime,
                           api_data_current: bool) -> ConsumerValidatedTrend:
    record = _mapping(value)
    rank = record.get("rank")
    if not isinstance(rank, int) or rank < 1:
        raise ValueError("Consumer validated Trend rank is malformed.")
    return ConsumerValidatedTrend(
        _required_text(record, "trend_name"),
        _required_text(record, "description"),
        rank,
        _required_text(record, "market_status"),
        _required_text(record, "evidence_summary"),
        tuple(_parse_video(item, api_data_current) for item in _records(record, "supporting_videos")),
        tuple(_parse_creator(item, now) for item in _records(record, "supporting_creators")),
        _required_text(record, "provenance_digest"),
    )


def _parse_creator(value: object, now: datetime) -> ConsumerCreator:
    record = _mapping(value)
    expires_at = datetime.fromisoformat(_required_text(record, "identity_expires_at").replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        raise ValueError("Consumer creator identity expiry is malformed.")
    if expires_at.astimezone(UTC) <= now:
        return ConsumerCreator(display_name=None)
    tracking_key = _required_text(record, "tracking_key")
    if not tracking_key.startswith("creator-opportunity-handle-"):
        raise ValueError("Consumer creator tracking key is malformed.")
    return ConsumerCreator(
        _optional_text(record.get("display_name")), _optional_text(record.get("public_handle")),
        _optional_text(record.get("public_creator_locator")), tracking_key,
    )


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Consumer snapshot timestamp is malformed.")
    return parsed.astimezone(UTC)


def display_timestamp(value: str) -> str:
    """Format an already-safe snapshot time for consumer presentation."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Recently"
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
