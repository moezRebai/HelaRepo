---
name: pr-review
description: >-
  Use whenever someone wants an existing code change reviewed or vetted before it
  merges — a pull request, merge request, PR/MR, a git/branch diff, or pasted
  changed files. THE skill for review requests in any wording: "review my PR/MR",
  "look over these changes", "sanity check this before I merge", "take a look at
  this diff", "leave comments on anything sketchy", checking a change for
  bugs/security before it lands, or
  dropping a GitLab/Bitbucket PR/MR URL for feedback. Also for posting findings
  as inline comments, or a review report grouped by severity. Works with GitLab
  MRs and Bitbucket PRs via their REST APIs and with a local git diff; judges
  correctness, security, dependencies, tests, readability, and team standards
  (strongest on Bash, Python, YAML/CI), drafts a report, and — only after you
  confirm — posts inline comments. Do NOT use for writing new code, refactoring,
  fixing a known bug, running tests, or doing a migration yourself — only for
  reviewing a change that already exists.
---

# PR / MR Review

Review a code change the way a careful senior teammate would: understand what it
is trying to do, read enough surrounding code to judge it in context, find the
problems that actually matter, and communicate them in a way the author can act
on. Then, only after the human running the review approves, post the findings
back to the PR/MR.

This team's code is primarily **Bash/shell, Python, and YAML (including CI
pipeline definitions)**, often in the context of a Bitbucket→GitLab migration.
The review checklist is tuned for those; see `references/review-checklist.md`.

## The one rule that matters most

**Never post comments to a PR/MR without explicit confirmation from the person
running the review.** Draft the full report, show it, and wait for a clear "yes,
post it" (or "post only the blockers", etc.). Posting is outward-facing and hard
to undo — a wrong or noisy comment is visible to the whole team and emails the
author. Getting a human in the loop once is cheap; a bad batch of public
comments is not.

## Workflow

### 1. Identify the source of the diff

Figure out what you're reviewing from what the user gave you:

- **A GitLab MR URL** (`.../-/merge_requests/123`) → GitLab. See `references/gitlab.md`.
- **A Bitbucket PR URL** (`.../pull-requests/123`) → Bitbucket. See `references/bitbucket.md`.
- **No URL, "review my branch / this diff"** → local review against the base
  branch. Use `git diff <base>...HEAD` (ask which base if it isn't obvious;
  default to the repo's main/master or the branch's merge-base).

If the user hasn't said which, ask — don't guess between platforms.

### 2. Fetch the diff and the changed files

Get the raw diff, then **read the full changed files, not just the diff hunks.**
The diff shows *what* changed; the surrounding code tells you whether the change
is *correct*. A bug is frequently in the interaction between changed and
unchanged lines (a caller you didn't touch, a variable that's now shadowed, an
error path that's no longer reached).

- For GitLab / Bitbucket, use `scripts/fetch_diff.py` (unifies both platforms;
  see the reference files for auth env vars). It writes the diff plus the list of
  changed files.
- For a local diff, `git diff` plus reading the files directly.

Also read: the PR/MR **title and description** (states intent — review against
it), any linked issue, and the **tests** touched or that *should* have been.

### 3. Review against the checklist

Work through `references/review-checklist.md`, which is organized by concern
(correctness, security, dependencies, tests, readability/standards) and by
language (Bash, Python, YAML/CI). Don't mechanically apply every item — use it
as a memory aid so you don't miss a category, and spend your attention where the
change is actually risky.

Optional automated help — only if the tool is already installed (check with
`command -v`); do **not** install anything without asking:
- `shellcheck <file>` for Bash
- `ruff check <file>` and `bandit -r <file>` for Python
- `yamllint <file>` for YAML

Treat linter output as input to your judgment, not as the review itself. The
value you add is the reasoning a linter can't do — logic errors, missing edge
cases, wrong abstraction, security implications of *this* change in *this*
context.

**Always make an explicit call on test coverage** — this is the single easiest
thing to skip and the one authors most need pushed on. Any change with real logic
(a new function, a bug fix, a branch/condition) should come with a test, and a
bug fix in particular should add a test that would have caught the bug, or it can
silently return. Don't let a passing-looking diff lull you out of asking "what
proves this works, and what proves it stays working?" State your conclusion even
when it's positive ("the new parser is covered by `test_parse.py`") — the report
template below has a required line for it so it can't quietly fall off.

### 4. Write the report

Group findings by severity so the author knows what blocks merge vs. what's
optional. Use this structure:

```
# Review: <PR/MR title>

**Summary:** <2-4 sentences: what the change does, and your overall take —
approve / approve with nits / request changes.>

**Tests:** <One required line: are the changes tested? Name the covering tests, or
say what's missing and what test should be added. If tests genuinely aren't
warranted (e.g. a comment/config-only tweak), say that explicitly.>

## 🔴 Blockers (N)
Must fix before merge — bugs, security holes, broken behavior.

- **`path/to/file.sh:42`** — <what's wrong, why it matters, and the fix.>

## 🟠 Major (N)
Should fix — real problems that aren't strictly merge-blocking.

## 🟡 Minor (N)
Worth addressing — smaller correctness/readability issues.

## 🔵 Nits (N)
Optional — style, naming, polish. Prefix these clearly so they read as optional.

## ✅ What's good
Call out 1-3 things done well. This isn't filler — it tells the author what to
keep doing and makes the critical feedback land better.
```

Every finding gets a **`file:line` reference** and a concrete fix or a specific
question. "This could be cleaner" is useless; "extract lines 40-55 into a
`validate_config` function so the early-return errors are visible" is actionable.
Quote the offending line when it helps.

Calibrate severity honestly. Inflating nits to blockers trains the author to
ignore you; missing a real blocker is worse. If you're unsure whether something
is a bug, say so and frame it as a question rather than asserting a defect.

### 5. Confirm, then post

Show the report and ask how the user wants to proceed. Offer the natural
choices: post everything, post only blockers/majors, post nothing (report only),
or edit first. **Only after they confirm**, post inline comments using the
platform's API (see `references/gitlab.md` / `references/bitbucket.md`, or
`scripts/post_comments.py`). Anchor each comment to its `file:line`. After
posting, report back exactly what was posted and where.

## Style of feedback

- Be direct and specific, but collegial — you're reviewing the code, not the
  person. Prefer "this loops over `$files` unquoted, so it breaks on paths with
  spaces" over "you forgot to quote."
- Explain the *why* behind each finding. The author learns from the reasoning,
  and it lets them push back when your context is wrong.
- Don't pad the report with generic advice that isn't tied to this diff. A short
  report of real findings beats a long one padded with boilerplate.
- When the change is genuinely good, say so plainly and keep the report short.
  Not every review needs to find problems.
