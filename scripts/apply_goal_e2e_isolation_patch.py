from pathlib import Path

path = Path('.github/workflows/kesher-live-e2e-test.yml')
text = path.read_text(encoding='utf-8')
needle = """        env:\n          TARGET_SLUG: ${{ steps.source.outputs.slug }}\n          SOURCE_SHA: ${{ steps.source.outputs.source_content_sha256 }}\n          KESHER_STATE_DIR: ${{ env.KESHER_E2E_LONG_STATE_DIR }}\n        shell: bash\n"""
replacement = """        env:\n          TARGET_SLUG: ${{ steps.source.outputs.slug }}\n          SOURCE_SHA: ${{ steps.source.outputs.source_content_sha256 }}\n          KESHER_STATE_DIR: ${{ env.KESHER_E2E_LONG_STATE_DIR }}\n          KESHER_MEDIA_MODE: video_overview\n        shell: bash\n"""
if 'KESHER_MEDIA_MODE: video_overview' not in text:
    if text.count(needle) != 1:
        raise SystemExit(f'Expected one isolated Overview env block, found {text.count(needle)}')
    text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding='utf-8')
print('GOAL_E2E_LONG_FORM_MODE_PATCH_OK')
