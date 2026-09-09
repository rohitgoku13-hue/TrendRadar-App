"""Read-only consumer experience for the explicit completed Trend Radar result."""

from __future__ import annotations

import streamlit as st

from dashboard.consumer_product_read_model import (
    ConsumerCategory,
    ConsumerSubtrend,
    ConsumerTopic,
    ConsumerTrendRadarV1,
    ConsumerTrendRadarV1Projector,
    display_timestamp,
)
from dashboard.product_read_model import PublicProductReadModelLoader


SEP02_FREE_FACTUAL_V1_ARTIFACT_ID = "free-factual-v1-cad66614120dea9ddf92226975e1858632183ad740e1e6dee9f8fbf4a7baabb2"
SEP02_SEMANTIC_TREND_PIPELINE_ARTIFACT_ID = "semantic-trend-pipeline-9973028686f8bc577f18595378efa198a69a1f783884e8678ef4e3d22208296a"
SEP02_DEPLOYMENT_PRODUCT_PROJECTION_ARTIFACT_ID = "trend-radar-deployment-run-4671f23d51cd5db4f2c30e8236ade0d1e0600c2cb0b7a219cfba8f3cb99f8be0"
PRIVACY_POLICY_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/privacy.html"
TERMS_OF_SERVICE_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/terms.html"

st.set_page_config(page_title="Trend Radar", page_icon=":material/trending_up:", layout="wide")


def _route() -> tuple[str, ...]:
    return tuple(st.session_state.get("consumer_route", ("home",)))


def _go(*route: str) -> None:
    st.session_state.consumer_route = route
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
            st.write(f"{len(topic.subtrends)} discovered trend{'s' if len(topic.subtrends) != 1 else ''}")
            if st.button("View topic", key=f"topic-{category.category_label}-{topic.topic_label}"):
                _go("topic", category.category_label, topic.topic_label)


def _render_topic(topic: ConsumerTopic, category_label: str) -> None:
    st.title(topic.topic_label)
    if not topic.subtrends:
        st.info("No current trends are available for this topic. Trend Radar is still watching this space.")
        return
    for subtrend in topic.subtrends:
        with st.container(border=True):
            st.subheader(subtrend.display_label)
            st.write(f"{len(subtrend.videos)} videos · {len(subtrend.creators)} creators")
            if st.button("View trend", key=f"subtrend-{category_label}-{topic.topic_label}-{subtrend.display_label}"):
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
    consumer_snapshot = ConsumerTrendRadarV1Projector().project(source)
except ValueError:
    st.error("Trend Radar could not load the selected update.")
    st.stop()

with st.sidebar:
    if st.button("Home"):
        _go("home")
    if st.button("About Trend Radar"):
        _go("about")
    st.divider()
    st.caption("Policies")
    st.markdown(
        f"[Privacy Policy]({PRIVACY_POLICY_URL}) · "
        f"[Terms of Service]({TERMS_OF_SERVICE_URL})"
    )

current_route = _route()
_breadcrumb(current_route)
_lookup(consumer_snapshot, current_route)
