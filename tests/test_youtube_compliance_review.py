from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from dashboard.compliance_review import build_compliance_review_snapshot
from dashboard.product_read_model import PublicProductReadModelLoader


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PRIVACY_POLICY_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/privacy.html"
TERMS_OF_SERVICE_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/terms.html"
FACTUAL_ID = "free-factual-v1-cad66614120dea9ddf92226975e1858632183ad740e1e6dee9f8fbf4a7baabb2"
SEMANTIC_ID = "semantic-trend-pipeline-9973028686f8bc577f18595378efa198a69a1f783884e8678ef4e3d22208296a"
PROJECTION_ID = "trend-radar-deployment-run-4671f23d51cd5db4f2c30e8236ade0d1e0600c2cb0b7a219cfba8f3cb99f8be0"


def _body(app: AppTest) -> str:
    values: list[str] = []
    for element_type in ("title", "header", "subheader", "markdown", "caption", "info", "warning", "success"):
        values.extend(str(item.value) for item in getattr(app.main, element_type))
    return "\n".join(values)


def _links(app: AppTest) -> dict[str, str]:
    return {item.proto.label: item.proto.url for item in app.get("link_button")}


def test_reviewer_projection_supports_a_hot_deploy_worker_with_prior_read_model_shape() -> None:
    source = PublicProductReadModelLoader().load(
        factual_artifact_id=FACTUAL_ID,
        semantic_artifact_id=SEMANTIC_ID,
        projection_artifact_id=PROJECTION_ID,
    )
    prior_shape = SimpleNamespace(
        explicit_gap_count=source.explicit_gap_count,
        creator_signals=source.creator_signals,
        semantic_state=source.semantic_state,
        cross_creator_signals=source.cross_creator_signals,
        validated_trends=source.validated_trends,
    )

    snapshot = build_compliance_review_snapshot(prior_shape)

    assert (
        snapshot.search_appearances,
        snapshot.unique_videos,
        snapshot.qualifying_videos,
        snapshot.qualified_creators,
        snapshot.sufficient_creator_histories,
    ) == (1_180, 1_165, 21, 13, 2)


def test_reviewer_page_loads_directly_from_a_reviewer_friendly_query() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=20)
    app.query_params["view"] = "youtube-api-review"
    app.run()

    assert not app.exception
    assert app.title[0].value == "YouTube API compliance review - sample analysis"
    body = _body(app)
    assert "Representative completed analysis using real retained YouTube API-derived evidence." in body
    assert "It is not the current live Trend Radar feed." in body


def test_reviewer_page_shows_exact_real_analytics_and_truthful_zero_result() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=20)
    app.query_params["view"] = "youtube-api-review"
    app.run()

    metrics = {item.label: item.value for item in app.metric}
    assert metrics == {
        "Search appearances": "1,180",
        "Unique videos": "1,165",
        "Qualifying videos": "21",
        "Qualified creators": "13",
        "Creator histories with sufficient evidence": "2",
        "Semantic creators": "13",
        "Valid Creator Patterns": "15",
        "Cross-Creator Signals": "1",
        "Validated Trends": "0",
    }
    body = _body(app)
    assert "SUCCESS_NO_VALIDATED_TRENDS" in body
    assert "does not manufacture a Trend" in body


def test_reviewer_page_documents_all_four_methods_and_six_anonymized_rows() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=20)
    app.query_params["view"] = "youtube-api-review"
    app.run()

    assert len(app.table) == 2
    api_table = app.table[0].value
    sample_table = app.table[1].value
    assert tuple(api_table["API method"]) == (
        "search.list",
        "videos.list",
        "channels.list",
        "playlistItems.list",
    )
    assert len(sample_table) == 6
    assert tuple(sample_table["Creator"]) == tuple(f"Creator {index:02d}" for index in range(1, 7))
    assert set(sample_table["Video result"]) == {"Qualified"}
    rendered = _body(app) + "\n" + api_table.to_string() + "\n" + sample_table.to_string()
    assert not any(
        value in rendered
        for value in (
            "creator-opportunity-handle-",
            "ephemeral-creator-",
            "GEMINI_API_KEY",
            "YOUTUBE_API_KEY",
            "D:\\",
        )
    )
    assert re.search(r"\bUC[A-Za-z0-9_-]{20,}\b", rendered) is None


def test_reviewer_page_shows_qualification_monitoring_and_policy_links() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=20)
    app.query_params["view"] = "youtube-api-review"
    app.run()

    body = _body(app)
    assert "factual eligibility and quality checks" in body
    assert "bounded set of recent public uploads" in body
    assert "independent evidence satisfies its validation requirements" in body
    assert "Recent public upload monitoring" in body
    assert "does not repeatedly use Search" in body
    assert _links(app) == {
        "Privacy Policy": PRIVACY_POLICY_URL,
        "Terms of Service": TERMS_OF_SERVICE_URL,
    }


def test_review_narrative_does_not_publish_numeric_decision_rules() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=20)
    app.query_params["view"] = "youtube-api-review"
    app.run()

    assert not app.exception
    # Aggregate metrics and retained record observations are separate elements.
    narrative = "\n".join(item.value for item in app.main.markdown)
    assert re.search(r"\d|[%≥≤<>]", narrative) is None


def test_normal_home_uses_current_consumer_snapshot_without_api_review_copy() -> None:
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Trend Radar"
    assert "Explore categories" in tuple(item.value for item in app.header)
    assert len(app.button) > 10
    body = _body(app)
    assert "search.list" not in body
    assert "Creator Patterns" not in body
    assert "SUCCESS_NO_VALIDATED_TRENDS" not in body


def test_about_page_links_to_the_reviewer_sample_without_changing_consumer_copy() -> None:
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.button[1].click().run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "About Trend Radar"
    review_button = next(button for button in app.button if button.label == "Open YouTube API compliance sample")
    body = _body(app)
    assert "does not access private YouTube account data" in body
    assert "search.list" not in body

    review_button.click().run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "YouTube API compliance review - sample analysis"
