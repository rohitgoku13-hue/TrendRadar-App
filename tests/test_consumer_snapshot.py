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
SNAPSHOT_ID = "consumer-trend-radar-candidate-4ee3b29e58ad729e1a8cd0b82a10a6d30a1d25da6a861fdc85d8d1dad808c57a"
SNAPSHOT_PATH = ROOT / "storage" / "deployment" / "consumer_snapshots" / f"{SNAPSHOT_ID}.json"


def _creators(snapshot):
    return tuple(
        creator
        for category in snapshot.categories
        for topic in category.topics
        for subtrend in topic.subtrends
        for creator in subtrend.creators
    )


def test_current_snapshot_is_complete_and_consumer_readable() -> None:
    snapshot = ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=SNAPSHOT_ID,
        evaluation_time=datetime(2026, 9, 16, tzinfo=UTC),
    )

    assert snapshot.coverage_state == "COMPLETE"
    assert len(snapshot.categories) == 9
    assert sum(len(category.topics) for category in snapshot.categories) == 145
    assert sum(
        len(topic.subtrends)
        for category in snapshot.categories
        for topic in category.topics
    ) == 145
    assert len(_creators(snapshot)) == 145
    assert all(creator.display_name for creator in _creators(snapshot))


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
