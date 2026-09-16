from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from dashboard.consumer_product_read_model import (
    CONSUMER_SNAPSHOT_SCHEMA_VERSION,
    ConsumerTrendRadarV1SnapshotLoader,
    IDENTITY_REFRESH_COPY,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID = "consumer-trend-radar-candidate-3453e57a12ac233962f3451a4f8cea5c46815c2054711912de67411858944ced"
SNAPSHOT_PATH = ROOT / "storage" / "deployment" / "consumer_snapshots" / f"{SNAPSHOT_ID}.json"


def _creators(snapshot):
    return tuple(
        creator
        for category in snapshot.categories
        for topic in category.topics
        for subtrend in topic.subtrends
        for creator in subtrend.creators
    )


def _videos(snapshot):
    return tuple(
        video
        for category in snapshot.categories
        for topic in category.topics
        for subtrend in topic.subtrends
        for video in subtrend.videos
    )


def _validated_trends(snapshot):
    return tuple(
        trend
        for category in snapshot.categories
        for topic in category.topics
        for trend in topic.validated_trends
    )


def test_current_snapshot_is_complete_and_consumer_readable() -> None:
    snapshot = ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=SNAPSHOT_ID,
        evaluation_time=datetime(2026, 9, 16, tzinfo=UTC),
    )

    assert snapshot.coverage_state == "COMPLETE"
    assert len(snapshot.categories) == 9
    assert sum(len(category.topics) for category in snapshot.categories) == 38
    assert sum(
        len(topic.subtrends)
        for category in snapshot.categories
        for topic in category.topics
    ) == 38
    # One creator supplied evidence to two source niches; consolidation keeps
    # the creator once within its consumer topic instead of duplicating cards.
    assert len(_creators(snapshot)) == 144
    assert all(creator.display_name for creator in _creators(snapshot))
    assert tuple(trend.trend_name for trend in _validated_trends(snapshot)) == (
        "Episodic Series Titling", "Music Content Metadata Pattern",
    )
    assert all(len(trend.creators) == 3 for trend in _validated_trends(snapshot))


def test_expired_creator_identities_are_anonymized_at_read_time() -> None:
    snapshot = ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=SNAPSHOT_ID,
        evaluation_time=datetime(2030, 1, 1, tzinfo=UTC),
    )

    creators = _creators(snapshot)
    assert creators
    assert all(creator.safe_display_name == IDENTITY_REFRESH_COPY for creator in creators)
    assert all(
        creator.public_handle is None
        and creator.public_creator_locator is None
        and creator.tracking_key is None
        for creator in creators
    )
    assert all(creator.subscriber_count is None for creator in creators)
    assert _videos(snapshot)
    assert all(video.views is None and video.published_at is None
               and video.thumbnail_locator is None and video.public_video_locator is None
               for video in _videos(snapshot))


def test_retention_bound_fields_are_available_before_and_withheld_at_exact_expiry() -> None:
    before = ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=SNAPSHOT_ID,
        evaluation_time=datetime(2026, 10, 6, 10, 47, 28, 399354, tzinfo=UTC),
    )
    at_expiry = ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=SNAPSHOT_ID,
        evaluation_time=datetime(2026, 10, 6, 10, 47, 28, 399355, tzinfo=UTC),
    )

    assert any(video.views is not None for video in _videos(before))
    assert all(creator.display_name for creator in _creators(before))
    assert all(video.views is None and video.public_video_locator is None for video in _videos(at_expiry))
    assert all(creator.display_name is None and creator.tracking_key is None for creator in _creators(at_expiry))
    assert all(
        video.views is None and video.public_video_locator is None
        for trend in _validated_trends(at_expiry)
        for video in trend.videos
    )
    assert all(
        creator.display_name is None and creator.public_creator_locator is None
        for trend in _validated_trends(at_expiry)
        for creator in trend.creators
    )


def test_snapshot_has_exact_immutable_identity_and_no_private_methodology() -> None:
    payload = SNAPSHOT_PATH.read_text(encoding="utf-8").casefold()

    assert CONSUMER_SNAPSHOT_SCHEMA_VERSION in payload
    assert all(
        marker not in payload
        for marker in (
            "api_key", "authorization", "channel_id", "video_id", "gemini",
            "prompt_version", "methodology", "planner", "saturation", "d:\\",
        )
    )
    ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=SNAPSHOT_ID,
        evaluation_time=datetime(2026, 9, 16, tzinfo=UTC),
    )


def test_snapshot_loader_rejects_a_wrong_identity(tmp_path: Path) -> None:
    wrong_id = "consumer-trend-radar-candidate-" + "0" * 64
    (tmp_path / f"{wrong_id}.json").write_bytes(SNAPSHOT_PATH.read_bytes())
    with pytest.raises(ValueError, match="immutable identity"):
        ConsumerTrendRadarV1SnapshotLoader(tmp_path).load(
            snapshot_id=wrong_id,
            evaluation_time=datetime(2026, 9, 16, tzinfo=UTC),
        )
