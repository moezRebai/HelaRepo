# GitLab merge requests

How to fetch an MR diff and post review comments on GitLab (gitlab.com or a
self-hosted instance). Two paths: the `glab` CLI if installed, otherwise the
REST API via `curl`/Python. `glab` is usually **not** installed here — assume
the API path and only use `glab` if `command -v glab` succeeds.

## Auth

Set a personal/project access token with `api` scope:

- `GITLAB_TOKEN` — the token
- `GITLAB_HOST` — base URL, e.g. `https://gitlab.com` or `https://gitlab.mycorp.com`
  (default `https://gitlab.com`)

If the token isn't set, ask the user for it (or to export it) rather than
guessing. Never print the token.

## Parsing the MR URL

`https://<host>/<group>/<project>/-/merge_requests/<iid>`

The API needs the URL-encoded project path and the MR `iid`. For
`https://gitlab.com/acme/tools/-/merge_requests/42`:
- project = `acme/tools` → URL-encoded `acme%2Ftools`
- iid = `42`

## Fetch the diff (REST API)

```bash
# MR metadata (title, description, source/target branch, SHAs)
curl -sf --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_HOST/api/v4/projects/acme%2Ftools/merge_requests/42"

# The changes (diffs per file)
curl -sf --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_HOST/api/v4/projects/acme%2Ftools/merge_requests/42/changes"
```

`changes` returns `changes[]` with `old_path`, `new_path`, `diff`, plus
`diff_refs` (`base_sha`, `head_sha`, `start_sha`) which you need to anchor
inline comments. `scripts/fetch_diff.py` wraps this.

To read full file contents at the MR head (for context beyond the hunks):

```bash
curl -sf --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_HOST/api/v4/projects/acme%2Ftools/repository/files/path%2Fto%2Ffile.py/raw?ref=<head_sha>"
```

## Post inline comments (only after user confirmation)

Inline comments are **discussions** with a `position`. You need `diff_refs` from
the MR (base/head/start SHA).

```bash
curl -sf --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_HOST/api/v4/projects/acme%2Ftools/merge_requests/42/discussions" \
  --data-urlencode "body=**Blocker:** \`\$dir\` is unquoted; breaks on paths with spaces." \
  --data "position[position_type]=text" \
  --data "position[base_sha]=<base_sha>" \
  --data "position[head_sha]=<head_sha>" \
  --data "position[start_sha]=<start_sha>" \
  --data "position[new_path]=scripts/deploy.sh" \
  --data "position[new_line]=42"
```

- Comment on an **added/changed** line → set `new_path` + `new_line`.
- Comment on a **removed/context** line → set `old_path` + `old_line`.
- If anchoring fails (line not in the diff), fall back to a general MR note:
  ```bash
  curl -sf --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    "$GITLAB_HOST/api/v4/projects/acme%2Ftools/merge_requests/42/notes" \
    --data-urlencode "body=..."
  ```

A **summary comment** (the report overview) is best posted as a single MR note
(the `notes` endpoint above), with the per-finding items as inline discussions.

## glab CLI (only if installed)

```bash
glab mr diff 42
glab mr view 42
# glab has no first-class inline-comment command; use the API for those.
```

## After posting

Report back the discussion/note IDs or URLs so the user can find them, and
confirm the count (e.g. "posted 3 inline comments + 1 summary note on MR !42").
