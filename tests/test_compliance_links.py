from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PRIVACY_POLICY_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/privacy.html"
TERMS_OF_SERVICE_URL = "https://rohitgoku13-hue.github.io/trendradar-compliance/terms.html"


def _policy_links(app: AppTest) -> dict[str, str]:
    return {item.proto.label: item.proto.url for item in app.get("link_button")}


def test_public_app_exposes_policy_links_with_current_home_content() -> None:
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Trend Radar"
    assert [item.value for item in app.header[:1]] == ["Explore categories"]
    assert [item.value for item in app.info] == [
        "No validated content trends are currently available."
    ]
    assert len([button for button in app.button if button.label == "View validated trend"]) == 0
    assert len([button for button in app.button if button.label == "Explore"]) == 9
    sidebar_markdown = "\n".join(item.value for item in app.sidebar.markdown)
    assert f"[Privacy Policy]({PRIVACY_POLICY_URL})" in sidebar_markdown
    assert f"[Terms of Service]({TERMS_OF_SERVICE_URL})" in sidebar_markdown


def test_about_page_has_current_product_copy_and_exact_policy_destinations() -> None:
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.button[1].click().run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "About Trend Radar"
    body = "\n".join(item.value for item in app.main.markdown)
    assert "emerging topics, content niches" in body
    assert "previously discovered creators" in body
    assert "does not access private YouTube account data" in body
    assert not any(
        prohibited in body
        for prohibited in (
            "Gemini",
            "quota",
            "checkpoint",
            "registry",
            "retention",
            "factual qualification",
        )
    )
    assert _policy_links(app) == {
        "Privacy Policy": PRIVACY_POLICY_URL,
        "Terms of Service": TERMS_OF_SERVICE_URL,
    }
