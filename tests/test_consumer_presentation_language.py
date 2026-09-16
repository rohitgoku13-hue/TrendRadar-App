from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_content_niches_are_not_presented_as_validated_trends() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "discovered content" in source
    assert '"View content niche"' in source
    assert "No current content niches are available" in source
    assert "discovered trend" not in source
    assert '"View trend"' not in source
