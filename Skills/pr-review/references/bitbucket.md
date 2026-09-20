# Bitbucket pull requests

How to fetch a PR diff and post review comments on Bitbucket. Covers **Bitbucket
Cloud** (bitbucket.org) primarily; notes for **Server/Data Center** at the end.
There's no CLI assumed — use the REST API via `curl`/Python.

## Auth (Bitbucket Cloud)

Bitbucket Cloud uses an **app password** (or API token) with Basic auth:

- `BITBUCKET_USER` — your username
- `BITBUCKET_APP_PASSWORD` — app password with `Pull requests: read/write` and
  `Repositories: read` scopes

Use `-u "$BITBUCKET_USER:$BITBUCKET_APP_PASSWORD"`. If unset, ask the user to
export them. Never print the app password.

## Parsing the PR URL

`https://bitbucket.org/<workspace>/<repo>/pull-requests/<id>`

For `https://bitbucket.org/acme/tools/pull-requests/42`:
- workspace = `acme`, repo = `tools`, id = `42`

## Fetch the diff (Cloud REST API v2.0)

```bash
BASE="https://api.bitbucket.org/2.0/repositories/acme/tools/pullrequests/42"

# PR metadata (title, description, source/dest branch, commit hashes)
curl -sf -u "$BITBUCKET_USER:$BITBUCKET_APP_PASSWORD" "$BASE"

# Raw unified diff
curl -sf -u "$BITBUCKET_USER:$BITBUCKET_APP_PASSWORD" "$BASE/diff"

# Structured diffstat (list of changed files + status)
curl -sf -u "$BITBUCKET_USER:$BITBUCKET_APP_PASSWORD" "$BASE/diffstat"
```

`scripts/fetch_diff.py` wraps this. To read a full file at the PR source commit
for context:

```bash
curl -sf -u "$BITBUCKET_USER:$BITBUCKET_APP_PASSWORD" \
  "https://api.bitbucket.org/2.0/repositories/acme/tools/src/<source_commit>/path/to/file.py"
```

## Post inline comments (only after user confirmation)

Inline comments anchor to a file + line via the `inline` object. The `to` field
is the line number in the **destination/new** file; `from` is the old file.

```bash
curl -sf -u "$BITBUCKET_USER:$BITBUCKET_APP_PASSWORD" \
  -X POST -H "Content-Type: application/json" \
  "$BASE/comments" \
  -d '{
        "content": {"raw": "**Blocker:** `$dir` is unquoted; breaks on paths with spaces."},
        "inline": {"path": "scripts/deploy.sh", "to": 42}
      }'
```

- Comment on an added/changed line → `"to": <new_line>`.
- Comment on a removed line → `"from": <old_line>`.
- A **summary comment** (report overview) → same endpoint with `content.raw`
  only, no `inline` object.

## Bitbucket Server / Data Center (self-hosted)

Different API (`/rest/api/1.0/...`) and Bearer-token auth:

- `BITBUCKET_TOKEN`, `BITBUCKET_HOST` (e.g. `https://bitbucket.mycorp.com`)

```bash
BASE="$BITBUCKET_HOST/rest/api/1.0/projects/ACME/repos/tools/pull-requests/42"
curl -sf -H "Authorization: Bearer $BITBUCKET_TOKEN" "$BASE"          # metadata
curl -sf -H "Authorization: Bearer $BITBUCKET_TOKEN" "$BASE.diff"     # diff
# inline comment:
curl -sf -H "Authorization: Bearer $BITBUCKET_TOKEN" \
  -X POST -H "Content-Type: application/json" "$BASE/comments" \
  -d '{"text":"...","anchor":{"path":"scripts/deploy.sh","line":42,"lineType":"ADDED","fileType":"TO"}}'
```

If you can't tell Cloud from Server from the URL, ask.

## After posting

Report the comment IDs/URLs and the count so the user can verify.
