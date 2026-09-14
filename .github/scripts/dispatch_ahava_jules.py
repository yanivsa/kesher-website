#!/usr/bin/env python3
import json
import os
import urllib.request

API = "https://jules.googleapis.com/v1alpha"
KEY = os.environ["JULES_API_KEY"]
TARGET = "yanivashdod-hub/Ahava"


def request(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


sources = request("GET", "/sources?pageSize=100").get("sources", [])
source_name = None
for item in sources:
    if TARGET.lower() in json.dumps(item, ensure_ascii=False).lower():
        candidate = item.get("name")
        if isinstance(candidate, str) and candidate.startswith("sources/"):
            source_name = candidate
            break

if not source_name:
    visible = [item.get("name") for item in sources if isinstance(item, dict)]
    raise SystemExit(f"Ahava source not found in Jules. Visible sources: {visible}")

print(f"Resolved Jules source: {source_name}")

prompt = r'''Work fully autonomously on the Android version of repository yanivashdod-hub/Ahava, starting from main. First inspect the actual repository and Android architecture; do not assume the cause before reading the code.

Goal: fix two focused Android usability problems when the Professor website/view is opened inside Ahava.

1) Professor width / zoom / horizontal navigation
The user currently mainly sees the right side of the page, cannot reach content on the left, cannot reach all topic selectors, and long questions/answers can be partially inaccessible.

Required behavior:
- Enable native two-finger pinch-to-zoom in and out in the Professor web content.
- Allow horizontal pan/scroll in BOTH directions when content is wider than the device.
- Preserve normal vertical scrolling, taps, inputs, authentication/session/cookies and links.
- All topic/category controls, complete question text and answer controls must be reachable.
- Preserve Hebrew/RTL. The initial horizontal position should make sense for RTL but must not lock the user to one side.
- Do not add permanent +/- zoom controls unless genuinely required.

Inspect both Android and web causes. Identify the actual Activity/Fragment/Compose screen/WebView wrapper and current WebView settings. Also inspect Professor HTML/CSS/viewport/touch handling for user-scalable=no, restrictive maximum-scale, fixed-width containers, overflow-x:hidden, JavaScript gesture prevention, or RTL horizontal positioning. Consider supportZoom, builtInZoomControls, displayZoomControls=false, useWideViewPort and loadWithOverviewMode only when appropriate to the real implementation.

2) Android system Back
Back currently appears to close/leave Ahava instead of navigating backward.

Required priority:
a. If the Professor WebView has navigable browser history, go back inside the WebView.
b. Otherwise leave Professor and return to the previous Ahava screen.
c. Otherwise use the app's normal navigation/back stack.
d. Exit/background normally only at the true app root when nothing remains to navigate.

Use the modern mechanism already present in the app (OnBackPressedDispatcher / Compose BackHandler/navigation as applicable). If Professor uses SPA navigation, verify whether WebView.canGoBack() accurately reflects history; account for history.pushState/popstate only if actually needed. Android gesture-back must coexist with horizontal webpage panning.

Before editing, determine and record in the session: root cause(s), files that need modification, and a short implementation plan based on actual code. Then implement only the smallest focused fix; do not refactor unrelated Ahava code.

Validation:
- Ahava home -> Professor -> topic/subject -> long question.
- Pan left and right across the full page width.
- Pinch zoom out and in.
- Vertical scrolling still works.
- Topic and answer taps still work.
- Full question text and all selectors/answers are reachable.
- Hebrew RTL remains correct.
- Repeated Back navigates question -> topic/previous Professor state -> Ahava screen and does not exit on the first Back.
- Test Android gesture navigation where applicable.
- Run relevant Android build/tests and existing CI-compatible checks.
- Confirm the normal web version is not broken.

Create one focused ready-for-review PR automatically if changes are required. The PR body must state root cause, changed files, exact behavior changed, tests/builds executed and results, and any remaining limitation. Keep the diff strictly limited to these two Android usability issues. Do not ask the user for confirmation or implementation choices.'''

payload = {
    "title": "Ahava Android Professor zoom, horizontal navigation and Back fix",
    "prompt": prompt,
    "sourceContext": {
        "source": source_name,
        "githubRepoContext": {"startingBranch": "main"},
    },
    "requirePlanApproval": False,
    "automationMode": "AUTO_CREATE_PR",
}

created = request("POST", "/sessions", payload)
print(json.dumps(created, ensure_ascii=False, indent=2))
name = created.get("name")
if not isinstance(name, str) or not name.startswith("sessions/"):
    raise SystemExit("Jules did not return a valid session name")
print(f"AHAVA_JULES_SESSION={name}")
