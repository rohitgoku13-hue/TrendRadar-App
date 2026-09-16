"""Read-only consumer experience for the explicit completed Trend Radar result."""

from __future__ import annotations

import streamlit as st

from dashboard.compliance_review import build_compliance_review_snapshot
from dashboard.consumer_product_read_model import (
    ConsumerCategory,
    ConsumerSubtrend,
    ConsumerTopic,
    ConsumerTrendRadarV1,
    ConsumerTrendRadarV1SnapshotLoader,
    ConsumerValidatedTrend,
    display_timestamp,
)
from dashboard.product_read_model import PublicProductReadModelLoader


SEP02_FREE_FACTUAL_V1_ARTIFACT_ID = "free-factual-v1-cad66614120dea9ddf92226975e1858632183ad740e1e6dee9f8fbf4a7baabb2"
SEP02_SEMANTIC_TREND_PIPELINE_ARTIFACT_ID = "semantic-trend-pipeline-9973028686f8bc577f18595378efa198a69a1f783884e8678ef4e3d22208296a"
SEP02_DEPLOYMENT_PRODUCT_PROJECTION_ARTIFACT_ID = "trend-radar-deployment-run-4671f23d51cd5db4f2c30e8236ade0d1e0600c2cb0b7a219cfba8f3cb99f8be0"
CURRENT_CONSUMER_SNAPSHOT_ID = "consumer-trend-radar-candidate-c1d2e98c30eff9f68c883693b88c69ef3ac6eb08818ec5b029b6bf2eefd90275"
PRIVACY_POLICY_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/privacy.html"
TERMS_OF_SERVICE_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/terms.html"
COMPLIANCE_REVIEW_QUERY_VALUE = "youtube-api-review"

st.set_page_config(page_title="Trend Radar", page_icon=":material/trending_up:", layout="wide")


def _route() -> tuple[str, ...]:
    route = st.session_state.get("consumer_route")
    if route is not None:
        return tuple(route)
    if st.query_params.get("view") == COMPLIANCE_REVIEW_QUERY_VALUE:
        return ("youtube-api-review",)
    return ("home",)


def _go(*route: str) -> None:
    st.session_state.consumer_route = route
    if route == ("youtube-api-review",):
        st.query_params["view"] = COMPLIANCE_REVIEW_QUERY_VALUE
    elif "view" in st.query_params:
        del st.query_params["view"]
    st.rerun()


def _breadcrumb(route: tuple[str, ...]) -> None:
    if route != ("home",):
        if st.button("← Back to home", key="back-home"):
            _go("home")


def _render_home(snapshot: ConsumerTrendRadarV1) -> None:
    st.title("Trend Radar")
    st.write("Discover what small creators are succeeding with right now.")
    st.caption(f"Last updated: {display_timestamp(snapshot.last_updated)}")
    if not snapshot.categories:
        st.info("No verified topics are available yet. Trend Radar is still watching this space.")
        return
    validated = tuple(
        (category.category_label, topic.topic_label, trend)
        for category in snapshot.categories
        for topic in category.topics
        for trend in topic.validated_trends
    )
    if validated:
        st.header("Validated trends")
        st.caption("Cross-creator trends supported by independent creator evidence.")
        for category_label, topic_label, trend in sorted(validated, key=lambda item: item[2].rank):
            with st.container(border=True):
                st.subheader(trend.trend_name)
                st.write(trend.description)
                st.caption(f"{category_label.replace('_', ' ').title()} · {trend.market_status}")
                if st.button("View validated trend", key=f"validated-{trend.provenance_digest}"):
                    _go("trend", category_label, topic_label, trend.trend_name)
    else:
        st.info("No validated content trends are currently available.")
    st.header("Explore categories")
    for category in snapshot.categories:
        with st.container(border=True):
            st.subheader(category.category_label)
            st.write(f"{len(category.topics)} discovered topic{'s' if len(category.topics) != 1 else ''}")
            if st.button("Explore", key=f"category-{category.category_label}"):
                _go("category", category.category_label)


def _render_category(category: ConsumerCategory) -> None:
    st.title(category.category_label)
    if not category.topics:
        st.info("No current topics are available in this category. Trend Radar is still watching this space.")
        return
    for topic in category.topics:
        with st.container(border=True):
            st.subheader(topic.topic_label)
            st.write(
                f"{len(topic.subtrends)} discovered content "
                f"niche{'s' if len(topic.subtrends) != 1 else ''}"
            )
            if st.button("View topic", key=f"topic-{category.category_label}-{topic.topic_label}"):
                _go("topic", category.category_label, topic.topic_label)


def _render_topic(topic: ConsumerTopic, category_label: str) -> None:
    st.title(topic.topic_label)
    if topic.validated_trends:
        st.header("Validated trends")
        for trend in topic.validated_trends:
            with st.container(border=True):
                st.subheader(trend.trend_name)
                st.write(trend.description)
                st.caption(trend.evidence_summary)
                if st.button("View validated trend", key=f"topic-validated-{trend.provenance_digest}"):
                    _go("trend", category_label, topic.topic_label, trend.trend_name)
    if not topic.subtrends:
        st.info("No current content niches are available for this topic. Trend Radar is still watching this space.")
        return
    for subtrend in topic.subtrends:
        with st.container(border=True):
            st.subheader(subtrend.display_label)
            st.write(f"{len(subtrend.videos)} videos · {len(subtrend.creators)} creators")
            if st.button(
                "View content niche",
                key=f"subtrend-{category_label}-{topic.topic_label}-{subtrend.display_label}",
            ):
                _go("subtrend", category_label, topic.topic_label, subtrend.display_label)


def _render_subtrend(subtrend: ConsumerSubtrend) -> None:
    st.title(subtrend.display_label)
    if not subtrend.videos:
        st.info("Supporting videos will appear here when they are available.")
        return
    for video in subtrend.videos:
        with st.container(border=True):
            if video.thumbnail_locator:
                st.image(video.thumbnail_locator)
            st.subheader(video.display_title)
            details = []
            if video.views is not None:
                details.append(f"{video.views:,} views")
            if video.published_at:
                details.append(f"Published {video.published_at}")
            if details:
                st.caption(" · ".join(details))
            if video.public_video_locator:
                st.link_button("Watch video", video.public_video_locator)
    if subtrend.creators:
        st.header("Creators")
        for creator in subtrend.creators:
            with st.container(border=True):
                st.subheader(creator.safe_display_name)
                if creator.public_handle:
                    st.caption(creator.public_handle)
                if creator.public_creator_locator:
                    st.link_button("View creator", creator.public_creator_locator)
                if creator.tracking_key:
                    st.button("Track creator", key=f"track-{creator.tracking_key}", disabled=True)
                    st.caption("Creator tracking will be available when you choose how to save your list.")


def _render_validated_trend(trend: ConsumerValidatedTrend) -> None:
    st.title(trend.trend_name)
    st.write(trend.description)
    st.caption(trend.market_status)
    st.info(trend.evidence_summary)
    st.header("Supporting videos")
    for video in trend.videos:
        with st.container(border=True):
            if video.thumbnail_locator:
                st.image(video.thumbnail_locator)
            st.subheader(video.display_title)
            details = []
            if video.views is not None:
                details.append(f"{video.views:,} views")
            if video.published_at:
                details.append(f"Published {video.published_at}")
            if details:
                st.caption(" · ".join(details))
            if video.public_video_locator:
                st.link_button("Watch video", video.public_video_locator)
    st.header("Independent creators")
    for creator in trend.creators:
        with st.container(border=True):
            st.subheader(creator.safe_display_name)
            if creator.public_handle:
                st.caption(creator.public_handle)
            if creator.public_creator_locator:
                st.link_button("View creator", creator.public_creator_locator)


def _render_compliance_review(source) -> None:
    sample = build_compliance_review_snapshot(source)

    st.title("YouTube API compliance review - sample analysis")
    st.info("Representative completed analysis using real retained YouTube API-derived evidence.")
    st.warning(
        "This historical review sample is provided for API compliance review. "
        "It is not the current live Trend Radar feed."
    )
    st.caption(f"Sample: {sample.sample_label}. Creator identities are anonymized for reviewer presentation.")

    st.header("A. Data retrieved")
    st.write(
        "Trend Radar uses public YouTube Data API metadata for bounded discovery, "
        "factual verification, creator qualification, and direct monitoring of known creators."
    )
    st.table(
        [
            {
                "API method": item.method,
                "Purpose": item.purpose,
                "Public fields used": item.fields_used,
            }
            for item in sample.api_methods
        ]
    )
    st.caption("No raw API response payloads, credentials, private account data, channel IDs, or video IDs are shown.")

    st.subheader("Representative retained records")
    st.table(
        [
            {
                "Creator": item.creator,
                "Public video title": item.title,
                "Published": item.published,
                "Views": f"{item.views:,}",
                "Subscriber observation": f"{item.subscribers:,}",
                "Category": item.category,
                "Video result": item.video_qualification,
                "Bounded history": item.history_result,
            }
            for item in sample.videos
        ]
    )
    st.caption("Views and subscriber counts are point-in-time retained observations, not live values.")

    st.header("B. Factual analytics")
    metrics = st.columns(4)
    metrics[0].metric("Search appearances", f"{sample.search_appearances:,}")
    metrics[1].metric("Unique videos", f"{sample.unique_videos:,}")
    metrics[2].metric("Qualifying videos", sample.qualifying_videos)
    metrics[3].metric("Qualified creators", sample.qualified_creators)

    st.markdown(
        "Trend Radar applies factual eligibility and quality checks to public video and channel "
        "metadata retrieved through the YouTube Data API. Only evidence satisfying those checks "
        "proceeds to creator-history analysis."
    )
    st.write(
        "Creator history is evaluated using a bounded set of recent public uploads. Where "
        "sufficient repeated-performance evidence exists, that evidence may proceed to "
        "creator-pattern analysis."
    )
    st.metric("Creator histories with sufficient evidence", sample.sufficient_creator_histories)

    st.header("C. Creator analytics")
    creator_metrics = st.columns(2)
    creator_metrics[0].metric("Semantic creators", sample.semantic_creators)
    creator_metrics[1].metric("Valid Creator Patterns", sample.valid_creator_patterns)
    st.write(
        "Repeated creator evidence is summarized into reviewable Creator Patterns. "
        "A pattern describes a recurring content mechanism; it does not by itself establish a cross-creator Trend."
    )

    st.header("D. Cross-creator analytics")
    st.metric("Cross-Creator Signals", sample.cross_creator_signals)
    st.write(
        "Equivalent pattern evidence across independent creators can form a Cross-Creator Signal. "
        "The completed sample produced one such signal, which was then evaluated under the final Trend rules."
    )

    st.header("E. End result")
    st.metric("Validated Trends", sample.validated_trends)
    st.success("Completed analysis: SUCCESS_NO_VALIDATED_TRENDS")
    st.write(
        "Cross-creator evidence proceeds through deterministic validation. Trend Radar publishes "
        "a Trend only when the available independent evidence satisfies its validation requirements. "
        "The completed analysis produced zero validated Trends. This is a valid end result. "
        "Trend Radar does not manufacture a Trend when evidence is insufficient."
    )
    st.markdown("**Consumer hierarchy:** Category → dynamically discovered Topic → Trend / Content Niche → Videos → Creators")
    st.caption("No sample Topic or Trend is shown because this completed execution produced no validated Trend.")

    st.header("F. Known-creator monitoring")
    monitoring_columns = st.columns(2)
    with monitoring_columns[0].container(border=True):
        st.subheader("Unknown or new creator")
        st.markdown("**Bounded Search discovery** → **factual verification**")
    with monitoring_columns[1].container(border=True):
        st.subheader("Known qualifying creator")
        st.markdown("**Recent public upload monitoring** → **video verification** → **channel metadata refresh when required**")
    st.info(
        "Known qualifying creators are monitored directly so Trend Radar does not repeatedly use "
        "Search simply to rediscover the same creator."
    )

    st.header("Policies")
    policy_columns = st.columns(2)
    with policy_columns[0]:
        st.link_button("Privacy Policy", PRIVACY_POLICY_URL)
    with policy_columns[1]:
        st.link_button("Terms of Service", TERMS_OF_SERVICE_URL)


def _lookup(snapshot: ConsumerTrendRadarV1, route: tuple[str, ...]) -> None:
    if route == ("home",):
        _render_home(snapshot)
        return
    if route == ("about",):
        st.title("About Trend Radar")
        st.write(
            "Trend Radar helps people explore emerging topics, content niches, "
            "high-performing public videos, and smaller creators gaining unusual traction."
        )
        st.write(
            "It uses current public YouTube metadata. Bounded discovery continues to find "
            "new creators, while previously discovered creators may be checked directly "
            "for new public uploads."
        )
        st.write(
            "Trend Radar does not access private YouTube account data or require private-account "
            "authorization, does not download video or audio, and is independent and not affiliated "
            "with, sponsored by, or endorsed by YouTube or Google."
        )
        policy_columns = st.columns(2)
        with policy_columns[0]:
            st.link_button("Privacy Policy", PRIVACY_POLICY_URL)
        with policy_columns[1]:
            st.link_button("Terms of Service", TERMS_OF_SERVICE_URL)
        if st.button("Open YouTube API compliance sample", icon=":material/fact_check:"):
            _go("youtube-api-review")
        st.caption(f"Last updated: {display_timestamp(snapshot.last_updated)}")
        return
    category = snapshot.category(route[1]) if len(route) > 1 else None
    if category is None:
        _go("home")
        return
    if route[0] == "category":
        _render_category(category)
        return
    topic = snapshot.topic(category.category_label, route[2]) if len(route) > 2 else None
    if topic is None:
        _go("category", category.category_label)
        return
    if route[0] == "topic":
        _render_topic(topic, category.category_label)
        return
    if route[0] == "trend":
        trend = snapshot.validated_trend(category.category_label, topic.topic_label, route[3]) if len(route) > 3 else None
        if trend is None:
            _go("topic", category.category_label, topic.topic_label)
            return
        _render_validated_trend(trend)
        return
    subtrend = snapshot.subtrend(category.category_label, topic.topic_label, route[3]) if len(route) > 3 else None
    if subtrend is None:
        _go("topic", category.category_label, topic.topic_label)
        return
    _render_subtrend(subtrend)


try:
    source = PublicProductReadModelLoader().load(
        factual_artifact_id=SEP02_FREE_FACTUAL_V1_ARTIFACT_ID,
        semantic_artifact_id=SEP02_SEMANTIC_TREND_PIPELINE_ARTIFACT_ID,
        projection_artifact_id=SEP02_DEPLOYMENT_PRODUCT_PROJECTION_ARTIFACT_ID,
    )
    consumer_snapshot = ConsumerTrendRadarV1SnapshotLoader().load(
        snapshot_id=CURRENT_CONSUMER_SNAPSHOT_ID,
    )
except ValueError:
    st.error("Trend Radar could not load the selected update.")
    st.stop()

with st.sidebar:
    if st.button("Home"):
        _go("home")
    if st.button("About Trend Radar"):
        _go("about")
    if st.button("YouTube API review sample", icon=":material/fact_check:"):
        _go("youtube-api-review")
    st.divider()
    st.caption("Policies")
    st.markdown(
        f"[Privacy Policy]({PRIVACY_POLICY_URL}) · "
        f"[Terms of Service]({TERMS_OF_SERVICE_URL})"
    )

current_route = _route()
_breadcrumb(current_route)
if current_route == ("youtube-api-review",):
    _render_compliance_review(source)
else:
    _lookup(consumer_snapshot, current_route)
