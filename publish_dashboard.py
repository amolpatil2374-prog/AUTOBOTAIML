"""
Publishes dashboard.html to a GitHub repo via the REST API, so GitHub Pages
serves it as a public URL reachable from anywhere (mobile data included) —
no git CLI, no local git repo, just plain HTTP calls using a personal
access token.

This step is deliberately non-fatal: if GitHub is unreachable or the token
is wrong, it logs the failure and run_daily.py continues — a publish
failure shouldn't be treated the same as a data-sync failure.
"""
import base64
import os

import requests

import config
from logging_setup import get_logger

log = get_logger("publish_dashboard", "publish_dashboard.log")

API_BASE = "https://api.github.com"
REMOTE_FILE_PATH = "index.html"  # so the root Pages URL works directly, no filename needed


def _headers():
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_existing_sha():
    """Returns the current file's SHA if it exists (needed to update it), else None.
    Raises a clear, specific error for anything else (bad token, rate limit,
    GitHub outage) rather than letting a raw HTTPError bubble up unexplained."""
    url = f"{API_BASE}/repos/{config.GITHUB_REPO}/contents/{REMOTE_FILE_PATH}"
    resp = requests.get(url, headers=_headers(), params={"ref": config.GITHUB_PAGES_BRANCH}, timeout=30)
    if resp.status_code == 200:
        return resp.json()["sha"]
    if resp.status_code == 404:
        return None  # file doesn't exist yet — this is the normal first-publish case
    if resp.status_code == 401:
        raise RuntimeError("GitHub rejected the token (401) — check GITHUB_TOKEN in config.py hasn't expired or been mistyped.")
    if resp.status_code == 403:
        raise RuntimeError(f"GitHub returned 403 — likely rate-limited or token lacks repo access. Response: {resp.text[:200]}")
    raise RuntimeError(f"Unexpected GitHub API response ({resp.status_code}): {resp.text[:200]}")


def publish(local_html_path):
    if not config.GITHUB_TOKEN or config.GITHUB_TOKEN.startswith("PASTE_"):
        log.warning("GITHUB_TOKEN not configured — skipping publish. See README for setup.")
        return False

    with open(local_html_path, "r", encoding="utf-8") as f:
        content = f.read()
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

    sha = _get_existing_sha()

    url = f"{API_BASE}/repos/{config.GITHUB_REPO}/contents/{REMOTE_FILE_PATH}"
    payload = {
        "message": "Update dashboard",
        "content": content_b64,
        "branch": config.GITHUB_PAGES_BRANCH,
    }
    if sha:
        payload["sha"] = sha  # required by GitHub's API when updating an existing file

    resp = requests.put(url, headers=_headers(), json=payload, timeout=30)
    if resp.status_code in (200, 201):
        log.info(f"Dashboard published successfully to {config.GITHUB_PAGES_URL}")
        return True
    else:
        log.error(f"Publish failed ({resp.status_code}): {resp.text[:300]}")
        return False


if __name__ == "__main__":
    dashboard_path = os.path.join(config.BASE_DIR, "dashboard.html")
    publish(dashboard_path)
