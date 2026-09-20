#!/usr/bin/env python3
"""Post review comments to a GitLab MR or Bitbucket PR.

RUN THIS ONLY AFTER THE USER HAS CONFIRMED they want comments posted. Posting is
public and emails the author; there is no bulk-undo.

Reads the metadata.json written by fetch_diff.py (for platform + anchor SHAs) and
a comments JSON file describing what to post:

  {
    "summary": "optional overall report posted as a single top-level comment",
    "inline": [
      {"path": "scripts/deploy.sh", "line": 42, "side": "new",
       "body": "**Blocker:** `$dir` is unquoted; breaks on paths with spaces."}
    ]
  }

  side: "new" (added/changed line, default) or "old" (removed/context line).

Usage:
  python post_comments.py --metadata pr_review_input/metadata.json \
                          --comments comments.json [--dry-run]

Env vars: same as fetch_diff.py.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _post(url, data, headers=None, auth=None, json_body=False):
    headers = dict(headers or {})
    if json_body:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    if auth:
        tok = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {tok}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}", file=sys.stderr)
        return None


def post_gitlab(meta, comments, dry):
    host = os.environ.get("GITLAB_HOST", "https://gitlab.com")
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        sys.exit("Set GITLAB_TOKEN")
    h = {"PRIVATE-TOKEN": token}
    proj = urllib.parse.quote(meta["project"], safe="")
    base = f"{host}/api/v4/projects/{proj}/merge_requests/{meta['iid']}"
    posted = 0

    if comments.get("summary"):
        if dry:
            print("[dry-run] summary note")
        else:
            _post(base + "/notes", {"body": comments["summary"]}, h)
        posted += 1

    for c in comments.get("inline", []):
        pos = {
            "position[position_type]": "text",
            "position[base_sha]": meta.get("base_sha"),
            "position[head_sha]": meta.get("head_sha"),
            "position[start_sha]": meta.get("start_sha"),
            "body": c["body"],
        }
        if c.get("side", "new") == "old":
            pos["position[old_path]"] = c["path"]
            pos["position[old_line]"] = c["line"]
        else:
            pos["position[new_path]"] = c["path"]
            pos["position[new_line]"] = c["line"]
        if dry:
            print(f"[dry-run] inline {c['path']}:{c['line']}")
        else:
            r = _post(base + "/discussions", pos, h)
            if r is None:  # fall back to a general note if anchoring failed
                _post(base + "/notes", {"body": f"`{c['path']}:{c['line']}` — {c['body']}"}, h)
        posted += 1
    return posted


def post_bitbucket_cloud(meta, comments, dry):
    user = os.environ.get("BITBUCKET_USER")
    pw = os.environ.get("BITBUCKET_APP_PASSWORD")
    if not (user and pw):
        sys.exit("Set BITBUCKET_USER and BITBUCKET_APP_PASSWORD")
    base = (f"https://api.bitbucket.org/2.0/repositories/"
            f"{meta['workspace']}/{meta['repo']}/pullrequests/{meta['id']}/comments")
    posted = 0
    if comments.get("summary"):
        if dry:
            print("[dry-run] summary comment")
        else:
            _post(base, {"content": {"raw": comments["summary"]}}, auth=(user, pw), json_body=True)
        posted += 1
    for c in comments.get("inline", []):
        key = "from" if c.get("side", "new") == "old" else "to"
        body = {"content": {"raw": c["body"]}, "inline": {"path": c["path"], key: c["line"]}}
        if dry:
            print(f"[dry-run] inline {c['path']}:{c['line']}")
        else:
            _post(base, body, auth=(user, pw), json_body=True)
        posted += 1
    return posted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--comments", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    meta = json.load(open(args.metadata, encoding="utf-8"))
    comments = json.load(open(args.comments, encoding="utf-8"))
    platform = meta.get("platform", "")

    if platform == "gitlab":
        n = post_gitlab(meta, comments, args.dry_run)
    elif platform == "bitbucket-cloud":
        n = post_bitbucket_cloud(meta, comments, args.dry_run)
    else:
        sys.exit(f"Posting for platform '{platform}' not implemented in this script; "
                 f"use the curl recipe in references/{platform.split('-')[0]}.md")

    verb = "Would post" if args.dry_run else "Posted"
    print(f"{verb} {n} comment(s) to {platform} PR/MR.")


if __name__ == "__main__":
    main()
