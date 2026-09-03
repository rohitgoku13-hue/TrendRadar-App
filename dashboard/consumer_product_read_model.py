"""Consumer-first, provider-independent projection for public Trend Radar pages.

This module accepts already-approved product results. It deliberately does
not infer a category, topic, video, or creator identity from aggregate
analytics. A future scanner publishes a complete ``ConsumerTrendRadarV1``
snapshot atomically; the current Sep02 result projects to an honest empty
catalog because it contains no consumer-safe taxonomy records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dashboard.product_read_model import PublicProductReadModel


IDENTITY_REFRESH_COPY = "Creator details will be available after the next refresh."


@dataclass(frozen=True, slots=True)
class ConsumerVideo:
    """A public video card supplied directly by an authoritative consumer snapshot."""

    display_title: str
    views: int | None = None
    published_at: str | None = None
    thumbnail_locator: str | None = None
    public_video_locator: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumerCreator:
    """A public creator card with no requirement to expose an internal identity."""

    display_name: str | None
    public_handle: str | None = None
    public_creator_locator: str | None = None
    tracking_key: str | None = None

    @property
    def safe_display_name(self) -> str:
        return self.display_name or IDENTITY_REFRESH_COPY


@dataclass(frozen=True, slots=True)
class ConsumerSubtrend:
    display_label: str
    videos: tuple[ConsumerVideo, ...]
    creators: tuple[ConsumerCreator, ...]


@dataclass(frozen=True, slots=True)
class ConsumerTopic:
    topic_label: str
    subtrends: tuple[ConsumerSubtrend, ...]


@dataclass(frozen=True, slots=True)
class ConsumerCategory:
    category_label: str
    topics: tuple[ConsumerTopic, ...]


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

    def subtrend(
        self,
        category_label: str,
        topic_label: str,
        subtrend_label: str,
    ) -> ConsumerSubtrend | None:
        topic = self.topic(category_label, topic_label)
        if topic is None:
            return None
        return next((item for item in topic.subtrends if item.display_label == subtrend_label), None)


class ConsumerTrendRadarV1Projector:
    """Build the current consumer snapshot without inventing taxonomy records."""

    def project(self, source: PublicProductReadModel) -> ConsumerTrendRadarV1:
        # The retained Sep02 public result provides an update timestamp and
        # completion state, but no category/topic/subtrend/video/creator cards.
        # A relationship summary is not promoted to a consumer Trend without an
        # already-authoritative consumer taxonomy record.
        coverage_state = "COMPLETE" if source.explicit_gap_count == 0 else "INCOMPLETE"
        return ConsumerTrendRadarV1(
            last_updated=source.last_updated,
            coverage_state=coverage_state,
            categories=(),
        )


def display_timestamp(value: str) -> str:
    """Format an already-safe snapshot time for consumer presentation."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Recently"
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
