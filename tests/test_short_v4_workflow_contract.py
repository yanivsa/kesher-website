from pathlib import Path


def test_short_v4_workflow_declares_article_short_media_mode():
    workflow = Path(".github/workflows/kesher-short-v4.yml").read_text(encoding="utf-8")
    assert 'KESHER_MEDIA_MODE: "article_short"' in workflow
