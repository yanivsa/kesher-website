from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Article worker: test-mode may keep its PR open only when explicitly authorized.
article = ".github/workflows/kesher-article-generation.yml"
replace_once(
    article,
    """      test_mode:\n        description: Authorized test — bypass same-date article/PR guard and isolate Jules session\n        required: false\n        default: false\n        type: boolean\n""",
    """      test_mode:\n        description: Authorized test — bypass same-date article/PR guard and isolate Jules session\n        required: false\n        default: false\n        type: boolean\n      keep_test_pr_open:\n        description: Authorized isolated E2E only — keep the test article PR open for downstream preview/media workers\n        required: false\n        default: false\n        type: boolean\n""",
)
replace_once(
    article,
    """          DISPATCH_SLOT: ${{ inputs.slot }}\n          DISPATCH_TEST_MODE: ${{ inputs.test_mode }}\n""",
    """          DISPATCH_SLOT: ${{ inputs.slot }}\n          DISPATCH_TEST_MODE: ${{ inputs.test_mode }}\n          DISPATCH_KEEP_TEST_PR_OPEN: ${{ inputs.keep_test_pr_open }}\n""",
)
replace_once(
    article,
    """            test_mode=\"true\"\n          else\n            slot=\"$DISPATCH_SLOT\"\n            test_mode=\"${DISPATCH_TEST_MODE:-false}\"\n          fi\n          if ! [[ \"$slot\" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then\n""",
    """            test_mode=\"true\"\n            keep_test_pr_open=\"false\"\n          else\n            slot=\"$DISPATCH_SLOT\"\n            test_mode=\"${DISPATCH_TEST_MODE:-false}\"\n            keep_test_pr_open=\"${DISPATCH_KEEP_TEST_PR_OPEN:-false}\"\n          fi\n          if [ \"$keep_test_pr_open\" = \"true\" ] && [ \"$test_mode\" != \"true\" ]; then\n            echo \"KEEP_TEST_PR_OPEN_REQUIRES_TEST_MODE\" >&2\n            exit 1\n          fi\n          if ! [[ \"$slot\" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then\n""",
)
replace_once(
    article,
    """          echo \"KESHER_TEST_MODE=$test_mode\" >> \"$GITHUB_ENV\"\n          echo \"Resolved slot=$slot test_mode=$test_mode\"\n""",
    """          echo \"KESHER_TEST_MODE=$test_mode\" >> \"$GITHUB_ENV\"\n          echo \"KESHER_KEEP_TEST_PR_OPEN=$keep_test_pr_open\" >> \"$GITHUB_ENV\"\n          echo \"Resolved slot=$slot test_mode=$test_mode keep_test_pr_open=$keep_test_pr_open\"\n""",
)
replace_once(
    article,
    """        if: ${{ always() && env.KESHER_TEST_MODE == 'true' && hashFiles('.kesher-article-result/result.json') != '' }}\n""",
    """        if: ${{ always() && env.KESHER_TEST_MODE == 'true' && env.KESHER_KEEP_TEST_PR_OPEN != 'true' && hashFiles('.kesher-article-result/result.json') != '' }}\n""",
)

# Long worker: production defaults stay identical, isolated tests get their own source + state namespace.
long_wf = ".github/workflows/kesher-daily-video.yml"
replace_once(
    long_wf,
    """      target_slug:\n        description: Exact article slug to generate video for\n        required: false\n        type: string\n""",
    """      target_slug:\n        description: Exact article slug to generate video for\n        required: false\n        type: string\n      source_ref:\n        description: Repository ref containing the authoritative article source\n        required: false\n        default: main\n        type: string\n      state_artifact_name:\n        description: Durable state artifact namespace\n        required: false\n        default: kesher-video-state\n        type: string\n""",
)
replace_once(
    long_wf,
    """  group: kesher-daily-notebooklm-video\n""",
    """  group: kesher-daily-notebooklm-video-${{ inputs.state_artifact_name || 'kesher-video-state' }}\n""",
)
replace_once(
    long_wf,
    """      KESHER_STATE_DIR: ${{ github.workspace }}/.kesher-video-state\n      NOTEBOOKLM_BIN: notebooklm\n""",
    """      KESHER_STATE_DIR: ${{ github.workspace }}/.kesher-video-state\n      KESHER_STATE_ARTIFACT: ${{ inputs.state_artifact_name || 'kesher-video-state' }}\n      KESHER_SOURCE_REF: ${{ inputs.source_ref || 'main' }}\n      NOTEBOOKLM_BIN: notebooklm\n""",
)
replace_once(
    long_wf,
    """      - name: Checkout current main\n        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n        with:\n          persist-credentials: false\n""",
    """      - name: Checkout authoritative source ref\n        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n        with:\n          ref: ${{ env.KESHER_SOURCE_REF }}\n          persist-credentials: false\n""",
)
long_text = Path(long_wf).read_text(encoding="utf-8")
long_text = long_text.replace("actions/artifacts?name=kesher-video-state&per_page=100", "actions/artifacts?name=${KESHER_STATE_ARTIFACT}&per_page=100")
long_text = long_text.replace("name: kesher-video-state\n          path: ${{ env.KESHER_STATE_DIR }}", "name: ${{ env.KESHER_STATE_ARTIFACT }}\n          path: ${{ env.KESHER_STATE_DIR }}")
long_text = long_text.replace(
    "if: ${{ github.event_name != 'pull_request' && (inputs.operation == 'full' || inputs.operation == 'generate') }}\n        env:\n          KESHER_RECOVERY_STATE_JSON:",
    "if: ${{ github.event_name != 'pull_request' && (inputs.operation == 'full' || inputs.operation == 'generate') && env.KESHER_STATE_ARTIFACT == 'kesher-video-state' }}\n        env:\n          KESHER_RECOVERY_STATE_JSON:",
    1,
)
Path(long_wf).write_text(long_text, encoding="utf-8")

# Short worker: isolate its own state and the long-form state it derives from.
short_wf = ".github/workflows/kesher-short-v4.yml"
replace_once(
    short_wf,
    """      historical_item_id:\n        description: Exact historical provider item id to adopt without regeneration\n        required: false\n        type: string\n""",
    """      historical_item_id:\n        description: Exact historical provider item id to adopt without regeneration\n        required: false\n        type: string\n      source_ref:\n        description: Repository ref containing the authoritative article source\n        required: false\n        default: main\n        type: string\n      state_artifact_name:\n        description: Durable Short state artifact namespace\n        required: false\n        default: kesher-short-v4-state\n        type: string\n      long_state_artifact_name:\n        description: Durable long-form state artifact namespace used for derivation\n        required: false\n        default: kesher-video-state\n        type: string\n""",
)
replace_once(
    short_wf,
    """  group: kesher-daily-article-short-v4\n""",
    """  group: kesher-daily-article-short-v4-${{ inputs.state_artifact_name || 'kesher-short-v4-state' }}\n""",
)
replace_once(
    short_wf,
    """      KESHER_STATE_DIR: ${{ github.workspace }}/.kesher-short-v4-state\n      KESHER_STATE_ARTIFACT: kesher-short-v4-state\n      NOTEBOOKLM_BIN: notebooklm\n""",
    """      KESHER_STATE_DIR: ${{ github.workspace }}/.kesher-short-v4-state\n      KESHER_STATE_ARTIFACT: ${{ inputs.state_artifact_name || 'kesher-short-v4-state' }}\n      KESHER_LONG_STATE_ARTIFACT: ${{ inputs.long_state_artifact_name || 'kesher-video-state' }}\n      KESHER_SOURCE_REF: ${{ inputs.source_ref || 'main' }}\n      NOTEBOOKLM_BIN: notebooklm\n""",
)
replace_once(
    short_wf,
    """      - name: Checkout current main for production\n        if: ${{ github.event_name != 'pull_request' }}\n        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n        with:\n          ref: main\n          persist-credentials: false\n""",
    """      - name: Checkout authoritative source ref for production or isolated E2E\n        if: ${{ github.event_name != 'pull_request' }}\n        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n        with:\n          ref: ${{ env.KESHER_SOURCE_REF }}\n          persist-credentials: false\n""",
)
short_text = Path(short_wf).read_text(encoding="utf-8")
short_text = short_text.replace("actions/artifacts?name=kesher-video-state&per_page=100", "actions/artifacts?name=${KESHER_LONG_STATE_ARTIFACT}&per_page=100")
short_text = short_text.replace("name: kesher-short-v4-state\n          path: ${{ env.KESHER_STATE_DIR }}", "name: ${{ env.KESHER_STATE_ARTIFACT }}\n          path: ${{ env.KESHER_STATE_DIR }}")
Path(short_wf).write_text(short_text, encoding="utf-8")

# Replace the old production-Controller live test with a fully isolated orchestrator.
live = r'''name: Kesher Live E2E Test
run-name: Kesher Isolated Live E2E ${{ inputs.slot }} — ${{ inputs.request_id }}

on:
  workflow_dispatch:
    inputs:
      slot:
        description: Israel date used by the isolated test article (YYYY-MM-DD)
        required: true
        type: string
      request_id:
        description: Unique lowercase id (letters, digits and hyphens)
        required: true
        type: string
      confirm:
        description: Type RUN_LIVE_E2E to authorize external Preview/YouTube publication
        required: true
        type: string

permissions:
  actions: write
  contents: read
  pull-requests: write

concurrency:
  group: kesher-live-e2e-test
  cancel-in-progress: false

jobs:
  live-e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 360
    env:
      GH_TOKEN: ${{ github.token }}
      SLOT: ${{ inputs.slot }}
      REQUEST_ID: ${{ inputs.request_id }}
      CONFIRM: ${{ inputs.confirm }}
    steps:
      - name: Checkout trusted main orchestrator
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: main
          fetch-depth: 0
          persist-credentials: false

      - name: Authorize isolated same-day E2E without touching daily production state
        id: auth
        run: |
          set -euo pipefail
          israel_today="$(TZ=Asia/Jerusalem date +%F)"
          test "$CONFIRM" = "RUN_LIVE_E2E"
          test "$SLOT" = "$israel_today" || {
            echo "Live E2E must use the current Israel date: $israel_today" >&2
            exit 1
          }
          [[ "$REQUEST_ID" =~ ^[a-z0-9][a-z0-9-]{2,30}$ ]] || {
            echo "request_id must be 3-31 lowercase letters/digits/hyphens" >&2
            exit 1
          }
          test -s public/images/signature/signature-mask.svg
          echo "video_artifact=kesher-e2e-video-${REQUEST_ID}" >> "$GITHUB_OUTPUT"
          echo "short_artifact=kesher-e2e-short-${REQUEST_ID}" >> "$GITHUB_OUTPUT"
          echo "preview_branch=e2e-${REQUEST_ID}" >> "$GITHUB_OUTPUT"
          echo "LIVE_E2E_ISOLATION_AUTHORIZED slot=$SLOT request_id=$REQUEST_ID"

      - name: Dispatch one isolated Jules article worker
        id: article_run
        run: |
          set -euo pipefail
          marker="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
          gh workflow run kesher-article-generation.yml --ref main \
            -f slot="$SLOT" \
            -f test_mode=true \
            -f keep_test_pr_open=true
          run_id=""
          for _ in $(seq 1 60); do
            run_id="$(gh run list --workflow kesher-article-generation.yml --event workflow_dispatch --limit 40 \
              --json databaseId,createdAt,displayTitle \
              --jq '.[] | select(.createdAt >= "'"$marker"'" and .displayTitle == "Kesher Article '"$SLOT"'") | .databaseId' | head -n1)"
            [ -n "$run_id" ] && break
            sleep 3
          done
          test -n "$run_id"
          echo "run_id=$run_id" >> "$GITHUB_OUTPUT"
          echo "LIVE_E2E_ARTICLE_RUN=$run_id"

      - name: Wait for isolated article PR and adopt its exact branch
        id: target
        env:
          ARTICLE_RUN_ID: ${{ steps.article_run.outputs.run_id }}
        run: |
          set -euo pipefail
          gh run watch "$ARTICLE_RUN_ID" --exit-status
          rm -rf /tmp/kesher-e2e-article
          mkdir -p /tmp/kesher-e2e-article
          gh run download "$ARTICLE_RUN_ID" -n "kesher-article-result-${ARTICLE_RUN_ID}" -D /tmp/kesher-e2e-article
          pr_url="$(python3 - <<'PY'
          import json
          from pathlib import Path
          paths = list(Path('/tmp/kesher-e2e-article').rglob('result.json'))
          if len(paths) != 1:
              raise SystemExit('Expected exactly one article result.json')
          payload = json.loads(paths[0].read_text(encoding='utf-8'))
          print(str(payload.get('pr_url') or '').strip())
          PY
          )"
          case "$pr_url" in
            https://github.com/${{ github.repository }}/pull/*) ;;
            *) echo "Unexpected isolated test PR URL: $pr_url" >&2; exit 1 ;;
          esac
          pr_number="${pr_url##*/}"
          source_ref="$(gh pr view "$pr_number" --json headRefName,state --jq 'select(.state == "OPEN") | .headRefName')"
          test -n "$source_ref"
          echo "pr_number=$pr_number" >> "$GITHUB_OUTPUT"
          echo "source_ref=$source_ref" >> "$GITHUB_OUTPUT"
          echo "LIVE_E2E_TEST_PR=$pr_number source_ref=$source_ref"

      - name: Generate trusted article image on the isolated PR
        id: image_run
        env:
          PR_NUMBER: ${{ steps.target.outputs.pr_number }}
        run: |
          set -euo pipefail
          marker="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
          gh workflow run kesher-article-image.yml --ref main -f pr_number="$PR_NUMBER"
          run_id=""
          for _ in $(seq 1 60); do
            run_id="$(gh run list --workflow kesher-article-image.yml --event workflow_dispatch --limit 40 \
              --json databaseId,createdAt,displayTitle \
              --jq '.[] | select(.createdAt >= "'"$marker"'" and .displayTitle == "Kesher Image PR '"$PR_NUMBER"'") | .databaseId' | head -n1)"
            [ -n "$run_id" ] && break
            sleep 3
          done
          test -n "$run_id"
          gh run watch "$run_id" --exit-status
          echo "run_id=$run_id" >> "$GITHUB_OUTPUT"

      - name: Checkout final isolated article source after image commit
        env:
          SOURCE_REF: ${{ steps.target.outputs.source_ref }}
        run: |
          set -euo pipefail
          git fetch --no-tags origin main "$SOURCE_REF"
          git checkout --detach "origin/$SOURCE_REF"

      - name: Resolve the one new article identity relative to main
        id: source
        run: |
          set -euo pipefail
          python3 - <<'PY' >> "$GITHUB_OUTPUT"
          import json
          import subprocess
          from pathlib import Path
          from scripts.kesher_daily_pipeline import source_metadata

          current = json.loads(Path('src/data/posts.json').read_text(encoding='utf-8'))
          base_raw = subprocess.check_output(['git', 'show', 'origin/main:src/data/posts.json'], text=True)
          base = json.loads(base_raw)
          base_slugs = {str(row.get('slug') or row.get('id') or '').strip() for row in base if isinstance(row, dict)}
          added = [row for row in current if isinstance(row, dict) and str(row.get('slug') or row.get('id') or '').strip() not in base_slugs]
          if len(added) != 1:
              raise SystemExit(f'Expected exactly one isolated article addition, found {len(added)}')
          meta = source_metadata(added[0])
          if str(added[0].get('date') or '')[:10] != '${{ inputs.slot }}':
              raise SystemExit('Isolated article date does not match requested slot')
          print(f"slug={meta['slug']}")
          print(f"content_sha256={meta['content_sha256']}")
          print(f"title={str(added[0].get('title') or '').replace(chr(10), ' ')}")
          PY
          echo "LIVE_E2E_SOURCE_IDENTITY_RESOLVED"

      - name: Set up Node for exact article quality and Preview build
        uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020
        with:
          node-version: 22
          cache: npm

      - name: Install web dependencies and Chromium
        run: |
          set -euo pipefail
          npm ci --no-audit --no-fund
          npx playwright install chromium

      - name: Run full quality gate on isolated article branch
        run: npm run check

      - name: Finalize Preview measurement placeholder
        env:
          VITE_GTM_CONTAINER_ID: ${{ secrets.VITE_GTM_CONTAINER_ID || 'disabled' }}
        run: |
          python3 - <<'PY'
          import os
          from pathlib import Path
          value = os.environ['VITE_GTM_CONTAINER_ID']
          for file in Path('dist').rglob('*.html'):
              text = file.read_text(encoding='utf-8')
              if '%VITE_GTM_CONTAINER_ID%' in text:
                  file.write_text(text.replace('%VITE_GTM_CONTAINER_ID%', value), encoding='utf-8')
          PY

      - name: Deploy isolated Cloudflare Pages Preview
        id: deploy_preview
        uses: cloudflare/wrangler-action@ebbaa1584979971c8614a24965b4405ff95890e0
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          wranglerVersion: 4.100.0
          command: pages deploy dist --project-name=kesher-website --branch=${{ steps.auth.outputs.preview_branch }}

      - name: Verify public Preview article
        id: preview
        env:
          PREVIEW_BRANCH: ${{ steps.auth.outputs.preview_branch }}
          SOURCE_SLUG: ${{ steps.source.outputs.slug }}
        run: |
          set -euo pipefail
          preview_url="https://${PREVIEW_BRANCH}.kesher-website.pages.dev/blog/${SOURCE_SLUG}"
          ok=false
          for _ in $(seq 1 30); do
            code="$(curl -L -sS -o /tmp/e2e-preview.html -w '%{http_code}' --max-time 30 "$preview_url" || true)"
            if [ "$code" = "200" ] && grep -F "${{ steps.source.outputs.title }}" /tmp/e2e-preview.html >/dev/null; then
              ok=true
              break
            fi
            sleep 4
          done
          test "$ok" = true
          echo "preview_url=$preview_url" >> "$GITHUB_OUTPUT"
          echo "LIVE_E2E_PREVIEW_URL=$preview_url"

      - name: Dispatch isolated production Overview worker
        id: long_run
        env:
          SOURCE_REF: ${{ steps.target.outputs.source_ref }}
          SOURCE_SLUG: ${{ steps.source.outputs.slug }}
          VIDEO_ARTIFACT: ${{ steps.auth.outputs.video_artifact }}
        run: |
          set -euo pipefail
          marker="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
          gh workflow run kesher-daily-video.yml --ref main \
            -f operation=full \
            -f target_slug="$SOURCE_SLUG" \
            -f source_ref="$SOURCE_REF" \
            -f state_artifact_name="$VIDEO_ARTIFACT"
          run_id=""
          for _ in $(seq 1 60); do
            run_id="$(gh run list --workflow kesher-daily-video.yml --event workflow_dispatch --limit 40 \
              --json databaseId,createdAt \
              --jq '.[] | select(.createdAt >= "'"$marker"'") | .databaseId' | head -n1)"
            [ -n "$run_id" ] && break
            sleep 3
          done
          test -n "$run_id"
          echo "run_id=$run_id" >> "$GITHUB_OUTPUT"
          echo "LIVE_E2E_OVERVIEW_RUN=$run_id"

      - name: Require exact public Overview from isolated state
        id: overview
        env:
          RUN_ID: ${{ steps.long_run.outputs.run_id }}
          VIDEO_ARTIFACT: ${{ steps.auth.outputs.video_artifact }}
          SOURCE_SLUG: ${{ steps.source.outputs.slug }}
          SOURCE_SHA: ${{ steps.source.outputs.content_sha256 }}
        run: |
          set -euo pipefail
          gh run watch "$RUN_ID" --exit-status
          rm -rf /tmp/kesher-e2e-long
          mkdir -p /tmp/kesher-e2e-long
          gh run download "$RUN_ID" -n "$VIDEO_ARTIFACT" -D /tmp/kesher-e2e-long
          python3 - <<'PY' >> "$GITHUB_OUTPUT"
          import json, os
          from pathlib import Path
          from scripts import kesher_content_controller as core
          from scripts import kesher_content_controller_v5 as v5
          paths = list(Path('/tmp/kesher-e2e-long').rglob('state.json'))
          if len(paths) != 1:
              raise SystemExit('Expected exactly one isolated long state.json')
          state = json.loads(paths[0].read_text(encoding='utf-8'))
          source = {'slug': os.environ['SOURCE_SLUG'], 'content_sha256': os.environ['SOURCE_SHA']}
          rows = v5._verified_exact(state, source)
          if len(rows) != 1:
              raise SystemExit(f'Expected one exact public Overview, found {len(rows)}')
          item = rows[0]
          if item.get('technical_verified') is not True:
              raise SystemExit('Overview lacks technical verification')
          print(f"long_item_id={item['id']}")
          print(f"youtube_url={item['youtube_url']}")
          PY
          echo "LIVE_E2E_OVERVIEW_PUBLIC=true"

      - name: Dispatch isolated production Short derivation worker
        id: short_run
        env:
          SOURCE_REF: ${{ steps.target.outputs.source_ref }}
          SOURCE_SLUG: ${{ steps.source.outputs.slug }}
          SOURCE_SHA: ${{ steps.source.outputs.content_sha256 }}
          LONG_ITEM_ID: ${{ steps.overview.outputs.long_item_id }}
          VIDEO_ARTIFACT: ${{ steps.auth.outputs.video_artifact }}
          SHORT_ARTIFACT: ${{ steps.auth.outputs.short_artifact }}
        run: |
          set -euo pipefail
          marker="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
          gh workflow run kesher-short-v4.yml --ref main \
            -f operation=derive \
            -f derive_slug="$SOURCE_SLUG" \
            -f derive_content_sha256="$SOURCE_SHA" \
            -f derive_long_item_id="$LONG_ITEM_ID" \
            -f source_ref="$SOURCE_REF" \
            -f state_artifact_name="$SHORT_ARTIFACT" \
            -f long_state_artifact_name="$VIDEO_ARTIFACT"
          run_id=""
          for _ in $(seq 1 60); do
            run_id="$(gh run list --workflow kesher-short-v4.yml --event workflow_dispatch --limit 40 \
              --json databaseId,createdAt \
              --jq '.[] | select(.createdAt >= "'"$marker"'") | .databaseId' | head -n1)"
            [ -n "$run_id" ] && break
            sleep 3
          done
          test -n "$run_id"
          echo "run_id=$run_id" >> "$GITHUB_OUTPUT"
          echo "LIVE_E2E_SHORT_RUN=$run_id"

      - name: Require exact public portrait Short with signature evidence
        id: short
        env:
          RUN_ID: ${{ steps.short_run.outputs.run_id }}
          SHORT_ARTIFACT: ${{ steps.auth.outputs.short_artifact }}
          SOURCE_SLUG: ${{ steps.source.outputs.slug }}
          SOURCE_SHA: ${{ steps.source.outputs.content_sha256 }}
        run: |
          set -euo pipefail
          gh run watch "$RUN_ID" --exit-status
          rm -rf /tmp/kesher-e2e-short
          mkdir -p /tmp/kesher-e2e-short
          gh run download "$RUN_ID" -n "$SHORT_ARTIFACT" -D /tmp/kesher-e2e-short
          python3 - <<'PY' >> "$GITHUB_OUTPUT"
          import json, os
          from pathlib import Path
          from scripts import kesher_content_controller as core
          from scripts import kesher_e2e_delivery_guard as guard
          paths = list(Path('/tmp/kesher-e2e-short').rglob('state.json'))
          if len(paths) != 1:
              raise SystemExit('Expected exactly one isolated Short state.json')
          state = json.loads(paths[0].read_text(encoding='utf-8'))
          source = {'slug': os.environ['SOURCE_SLUG'], 'content_sha256': os.environ['SOURCE_SHA']}
          rows = [row for row in state.get('items', []) if isinstance(row, dict) and guard.short_public_portrait_verified(row, source, youtube_verified=core.verified_youtube_item)]
          if len(rows) != 1:
              raise SystemExit(f'Expected one exact verified portrait Short, found {len(rows)}')
          print(f"youtube_url={rows[0]['youtube_url']}")
          PY
          echo "LIVE_E2E_SHORT_PUBLIC_PORTRAIT=true"

      - name: Re-verify both YouTube URLs publicly readable
        env:
          OVERVIEW_URL: ${{ steps.overview.outputs.youtube_url }}
          SHORT_URL: ${{ steps.short.outputs.youtube_url }}
        run: |
          python3 - "$OVERVIEW_URL" "$SHORT_URL" <<'PY'
          import json, sys, urllib.parse, urllib.request
          for label, url in (("Overview", sys.argv[1]), ("Short", sys.argv[2])):
              endpoint = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({'url': url, 'format': 'json'})
              with urllib.request.urlopen(endpoint, timeout=30) as response:
                  payload = json.load(response)
              if not str(payload.get('title') or '').strip():
                  raise SystemExit(f'{label} is not publicly readable')
              print(f'LIVE_E2E_{label.upper()}_OEMBED_OK url={url}')
          PY

      - name: Publish exact isolated E2E deliverables
        if: ${{ success() }}
        run: |
          {
            echo "### Kesher isolated live E2E — verified"
            echo
            echo "- article_preview_url: ${{ steps.preview.outputs.preview_url }}"
            echo "- overview_youtube_url: ${{ steps.overview.outputs.youtube_url }}"
            echo "- short_youtube_url: ${{ steps.short.outputs.youtube_url }}"
            echo "- source_slug: ${{ steps.source.outputs.slug }}"
            echo "- source_content_sha256: ${{ steps.source.outputs.content_sha256 }}"
            echo "- production_main_article_unchanged: true"
            echo "- production_controller_state_untouched: true"
          } >> "$GITHUB_STEP_SUMMARY"

      - name: Close isolated test article PR
        if: ${{ always() && steps.target.outputs.pr_number != '' }}
        env:
          PR_NUMBER: ${{ steps.target.outputs.pr_number }}
        run: |
          set -euo pipefail
          gh pr close "$PR_NUMBER" --comment "Isolated live E2E finished; this test article is intentionally not merged into production." || true
'''
Path(".github/workflows/kesher-live-e2e-test.yml").write_text(live, encoding="utf-8")

print("GOAL_E2E_ISOLATION_PATCH_APPLIED")
