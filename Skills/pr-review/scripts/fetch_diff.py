#!/usr/bin/env python3
"""Fetch a PR/MR diff and metadata from GitLab or Bitbucket into local files.

Detects the platform from the URL, calls the right REST API using tokens from the
environment, and writes:

  <out>/metadata.json   - title, description, branches, and the SHAs/commits
                          needed to anchor inline comments later
  <out>/diff.patch      - the unified diff
  <out>/changed_files.txt - one changed path per line

Usage:
  python fetch_diff.py <PR_OR_MR_URL> [--out DIR]

Env vars:
  GitLab:            GITLAB_TOKEN   (GITLAB_HOST defaults to https://gitlab.com)
  Bitbucket Cloud:   BITBUCKET_USER + BITBUCKET_APP_PASSWORD
  Bitbucket Server:  BITBUCKET_TOKEN + BITBUCKET_HOST

Only depends on the Python standard library (no requests/jq needed).
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request


def _get(url, headers=None, auth=None):
    req = urllib.request.Request(url, headers=headers or {})
    if auth:
        import base64
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} fetching {url}\n{e.read().decode('utf-8', 'replace')[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error fetching {url}: {e}")


def fetch_gitlab(url, out):
    m = re.match(r"(https?://[^/]+)/(.+?)/-/merge_requests/(\d+)", url)
    if not m:
        sys.exit("Could not parse GitLab MR URL")
    host, project, iid = m.group(1), m.group(2), m.group(3)
    host = os.environ.get("GITLAB_HOST", host)
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        sys.exit("Set GITLAB_TOKEN (personal/project access token with 'api' scope)")
    proj_enc = urllib.parse.quote(project, safe="")
    h = {"PRIVATE-TOKEN": token}
    api = f"{host}/api/v4/projects/{proj_enc}/merge_requests/{iid}"

    meta = json.loads(_get(api, h))
    changes = json.loads(_get(api + "/changes", h))
    refs = changes.get("diff_refs") or {}
    metadata = {
        "platform": "gitlab",
        "project": project,
        "iid": iid,
        "title": meta.get("title"),
        "description": meta.get("description"),
        "source_branch": meta.get("source_branch"),
        "target_branch": meta.get("target_branch"),
        "base_sha": refs.get("base_sha"),
        "head_sha": refs.get("head_sha"),
        "start_sha": refs.get("start_sha"),
    }
    diff_parts, files = [], []
    for c in changes.get("changes", []):
        path = c.get("new_path") or c.get("old_path")
        files.append(path)
        diff_parts.append(f"--- a/{c.get('old_path')}\n+++ b/{c.get('new_path')}\n{c.get('diff','')}")
    return metadata, "\n".join(diff_parts), files


def fetch_bitbucket(url, out):
    # Cloud
    m = re.match(r"https?://bitbucket\.org/([^/]+)/([^/]+)/pull-requests/(\d+)", url)
    if m:
        ws, repo, pid = m.groups()
        user = os.environ.get("BITBUCKET_USER")
        pw = os.environ.get("BITBUCKET_APP_PASSWORD")
        if not (user and pw):
            sys.exit("Set BITBUCKET_USER and BITBUCKET_APP_PASSWORD")
        base = f"https://api.bitbucket.org/2.0/repositories/{ws}/{repo}/pullrequests/{pid}"
        meta = json.loads(_get(base, auth=(user, pw)))
        diff = _get(base + "/diff", auth=(user, pw))
        diffstat = json.loads(_get(base + "/diffstat", auth=(user, pw)))
        files = []
        for v in diffstat.get("values", []):
            new = (v.get("new") or {}).get("path")
            old = (v.get("old") or {}).get("path")
            files.append(new or old)
        metadata = {
            "platform": "bitbucket-cloud",
            "workspace": ws, "repo": repo, "id": pid,
            "title": meta.get("title"),
            "description": (meta.get("description") or ""),
            "source_branch": (meta.get("source") or {}).get("branch", {}).get("name"),
            "target_branch": (meta.get("destination") or {}).get("branch", {}).get("name"),
            "source_commit": (meta.get("source") or {}).get("commit", {}).get("hash"),
        }
        return metadata, diff, files

    # Server / Data Center
    m = re.match(r"(https?://[^/]+)/projects/([^/]+)/repos/([^/]+)/pull-requests/(\d+)", url)
    if m:
        host, proj, repo, pid = m.groups()
        host = os.environ.get("BITBUCKET_HOST", host)
        token = os.environ.get("BITBUCKET_TOKEN")
        if not token:
            sys.exit("Set BITBUCKET_TOKEN (and BITBUCKET_HOST) for Bitbucket Server")
        h = {"Authorization": f"Bearer {token}"}
        base = f"{host}/rest/api/1.0/projects/{proj}/repos/{repo}/pull-requests/{pid}"
        meta = json.loads(_get(base, h))
        diff = _get(base + ".diff", h)
        metadata = {
            "platform": "bitbucket-server",
            "project": proj, "repo": repo, "id": pid,
            "title": meta.get("title"),
            "description": meta.get("description") or "",
            "source_branch": (meta.get("fromRef") or {}).get("displayId"),
            "target_branch": (meta.get("toRef") or {}).get("displayId"),
        }
        # crude file list from diff headers
        files = re.findall(r"^\+\+\+ b/(.+)$", diff, re.M)
        return metadata, diff, files

    sys.exit("Could not parse Bitbucket PR URL")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default="pr_review_input")
    args = ap.parse_args()

    if "/-/merge_requests/" in args.url:
        meta, diff, files = fetch_gitlab(args.url, args.out)
    elif "/pull-requests/" in args.url:
        meta, diff, files = fetch_bitbucket(args.url, args.out)
    else:
        sys.exit("URL is neither a GitLab MR (/-/merge_requests/) nor a Bitbucket PR (/pull-requests/)")

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    with open(os.path.join(args.out, "diff.patch"), "w", encoding="utf-8") as f:
        f.write(diff)
    with open(os.path.join(args.out, "changed_files.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(fp for fp in files if fp))

    print(f"Platform: {meta['platform']}")
    print(f"Title: {meta.get('title')}")
    print(f"{len([fp for fp in files if fp])} changed file(s). Wrote to {args.out}/")
    print("  metadata.json, diff.patch, changed_files.txt")


if __name__ == "__main__":
    main()
