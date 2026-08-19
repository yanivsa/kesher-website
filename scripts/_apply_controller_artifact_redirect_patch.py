#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/kesher_content_controller.py')
text = path.read_text(encoding='utf-8')
marker = '''    def contents_json(self, path: str, ref: str = "main") -> Any:\n'''
method = r'''    def download_artifact_archive(self, url: str) -> bytes:
        """Download an Actions artifact without forwarding GitHub auth to signed blob storage."""

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect())
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "kesher-content-controller",
        }
        last: Exception | None = None
        for attempt in range(4):
            request = urllib.request.Request(url, method="GET", headers=headers)
            try:
                with opener.open(request, timeout=45) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if not location:
                        raise ControllerError("GITHUB_ARTIFACT_REDIRECT_MISSING") from exc
                    signed_request = urllib.request.Request(
                        location,
                        method="GET",
                        headers={"User-Agent": "kesher-content-controller"},
                    )
                    try:
                        with urllib.request.urlopen(signed_request, timeout=60) as response:
                            return response.read()
                    except (urllib.error.HTTPError, urllib.error.URLError) as signed_exc:
                        last = signed_exc
                elif exc.code in {429, 500, 502, 503, 504}:
                    last = exc
                else:
                    detail = exc.read().decode("utf-8", errors="replace")[:1000]
                    raise ControllerError(
                        f"GITHUB_ARTIFACT_HTTP_{exc.code}: artifact download failed: {detail}"
                    ) from exc
            except urllib.error.URLError as exc:
                last = exc
            time.sleep(2 ** attempt)
        raise ControllerError(f"GITHUB_ARTIFACT_DOWNLOAD_FAILED: {last}")

'''
if 'def download_artifact_archive(' not in text:
    if text.count(marker) != 1:
        raise SystemExit('controller insertion marker not unique')
    text = text.replace(marker, method + marker, 1)
old = '                raw = self.request("GET", str(archive_url), raw=True)\n'
new = '                raw = self.download_artifact_archive(str(archive_url))\n'
if text.count(old) != 1:
    raise SystemExit('artifact download call target not unique')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
