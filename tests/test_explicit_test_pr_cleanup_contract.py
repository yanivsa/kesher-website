from pathlib import Path


def test_explicit_test_pr_is_auto_closed_to_avoid_same_date_collision():
    workflow = Path('.github/workflows/kesher-article-generation.yml').read_text(encoding='utf-8')
    assert 'pull-requests: write' in workflow
    assert 'Close explicit-test article PR to prevent same-date collision' in workflow
    assert "env.KESHER_TEST_MODE == 'true'" in workflow
    assert 'gh api --method PATCH' in workflow
    assert '-f state=closed' in workflow
    assert 'keep production source identity unique' in workflow


def test_cleanup_is_scoped_to_test_mode_only():
    workflow = Path('.github/workflows/kesher-article-generation.yml').read_text(encoding='utf-8')
    cleanup = workflow.split('Close explicit-test article PR to prevent same-date collision', 1)[1]
    cleanup = cleanup.split('Fail workflow when the article worker failed', 1)[0]
    assert "KESHER_TEST_MODE == 'true'" in cleanup
