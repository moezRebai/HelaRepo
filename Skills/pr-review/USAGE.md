# pr-review — team usage guide

A quick reference for using the `pr-review` skill. This file is for humans; Claude
loads `SKILL.md` automatically, not this.

## What it does

Reviews an existing code change — a GitLab merge request, a Bitbucket pull
request, or a local git branch diff — for correctness, security, dependencies,
tests, readability, and team standards (tuned for Bash, Python, and YAML/CI).
It drafts a severity-grouped report and, **only after you confirm**, posts the
findings as inline comments on the PR/MR.

It is *not* for writing new code, refactoring, fixing a known bug, running tests,
or doing a Bitbucket→GitLab migration yourself — only for reviewing a change that
already exists.

## How to trigger it

Just ask, in whatever phrasing is natural. Any of these work:

- "review this MR: https://gitlab.com/hela/tools/-/merge_requests/214"
- "can you look over my Bitbucket PR before I merge? <url>"
- "sanity check the diff on my current branch"
- "review these changes and post comments on the MR"
- "is this good to merge, or did I miss something?"

If you paste a URL it reviews that PR/MR; if you don't, it reviews your local
`git diff`.

## One-time auth setup (only needed to fetch/post from a remote)

The skill reads credentials from environment variables — it never stores them or
asks for them in chat. Set the ones for your platform before asking it to fetch a
remote PR/MR. Local-diff reviews need none of this.

| Platform | Environment variables | Token scope needed |
|----------|----------------------|--------------------|
| GitLab (gitlab.com or self-hosted) | `GITLAB_TOKEN`, and `GITLAB_HOST` if self-hosted (defaults to `https://gitlab.com`) | `api` |
| Bitbucket Cloud | `BITBUCKET_USER`, `BITBUCKET_APP_PASSWORD` | Pull requests: read/write; Repositories: read |
| Bitbucket Server / Data Center | `BITBUCKET_TOKEN`, `BITBUCKET_HOST` | PR read/write |

Set them for your shell session, e.g.:

```bash
# GitLab
export GITLAB_TOKEN="glpat-xxxxxxxx"
export GITLAB_HOST="https://gitlab.mycorp.com"   # omit for gitlab.com

# Bitbucket Cloud
export BITBUCKET_USER="you"
export BITBUCKET_APP_PASSWORD="xxxxxxxx"
```

PowerShell:

```powershell
$env:GITLAB_TOKEN = "glpat-xxxxxxxx"
```

If a variable is missing, the skill will ask you to export it rather than guess.

## What it does, step by step

1. **Identify the source** — GitLab MR (`/-/merge_requests/`), Bitbucket PR
   (`/pull-requests/`), or local diff. Asks if ambiguous.
2. **Fetch the change and its context** — pulls the diff, changed-file list, and
   PR/MR metadata, then reads the *full* changed files (not just the diff), plus
   the title/description and relevant tests.
3. **Review against the checklist** — correctness, security, dependencies, tests,
   readability/standards, plus language-specific checks for Bash/Python/YAML-CI.
   Runs `shellcheck`/`ruff`/`yamllint` as extra input if they happen to be
   installed.
4. **Draft the report** (shown in chat) — a summary + verdict, a required
   **Tests:** line, then findings grouped 🔴 Blockers / 🟠 Major / 🟡 Minor /
   🔵 Nits, each with a `file:line` reference and a concrete fix, plus a
   ✅ "What's good" section.
5. **Confirm, then post** — it never posts automatically. It asks whether to post
   everything / only blockers+majors / nothing / edit first, and only posts after
   you say so. Then it reports exactly what was posted and where.

For a **local diff** there is nothing to fetch or post, so it just prints the
report.

## Safety notes

- **Fetching is read-only; posting is the only write action, and it is gated on
  your explicit confirmation.** You can also ask for a dry run first.
- Treat any secret the review flags (e.g. a token committed to a pipeline file) as
  compromised — rotate it, don't just delete the line.

## Manual use of the helper scripts (optional)

The skill drives these for you, but you can run them directly:

```bash
# Fetch a diff + metadata into ./pr_review_input/
python scripts/fetch_diff.py "https://gitlab.com/hela/tools/-/merge_requests/214"

# Dry-run posting (prints what it WOULD post, posts nothing)
python scripts/post_comments.py \
  --metadata pr_review_input/metadata.json \
  --comments comments.json \
  --dry-run
```

## Not yet battle-tested

The remote fetch/post path is written to the documented GitLab/Bitbucket API
shapes but hasn't been run against a live instance. Before relying on it for the
team, do one smoke test: set your token, run `fetch_diff.py` on a real MR/PR URL,
then `post_comments.py --dry-run`.
