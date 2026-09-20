# Review checklist

A memory aid, not a script. Skim the whole thing so you don't forget a category,
then spend your attention where this particular change is risky. A one-line YAML
tweak doesn't need the full Python security pass; a new auth function does.

## Table of contents

- [Cross-cutting concerns](#cross-cutting-concerns)
- [Bash / shell](#bash--shell)
- [Python](#python)
- [YAML & CI pipelines](#yaml--ci-pipelines)
- [Dependencies](#dependencies)
- [Tests](#tests)

---

## Cross-cutting concerns

These apply regardless of language.

**Correctness**
- Does the change actually do what the title/description claims?
- Edge cases: empty input, zero/one/many, missing files, network failure,
  unexpected exit codes. What happens on the unhappy path?
- Off-by-one, inverted conditions, wrong comparison operators.
- Does it break any existing caller or downstream consumer not shown in the diff?
- Resource cleanup — files, connections, temp dirs, locks released on every path
  including error paths.

**Security**
- Secrets: no hardcoded tokens, passwords, keys, connection strings. Check they
  come from env/secret store, and that they aren't echoed/logged.
- Injection: any place user/external input reaches a shell, SQL, eval, or a
  string-built command.
- Path traversal, unsafe temp-file creation, overly broad file permissions.
- New external calls — is the endpoint trusted, is TLS verified?

**Readability / standards**
- Names say what the thing is/does. Consistent with surrounding code.
- Dead code, commented-out blocks, debug prints/`echo`s left behind.
- Complex logic has a short "why" comment (not a "what" comment restating code).
- Consistent with conventions already used in the file/module — match the
  neighbors rather than importing a different style.

---

## Bash / shell

Shell is where "looks fine" most often hides real bugs. Look hard here.

- **Unquoted expansions**: `$var`, `$(cmd)`, `${arr[@]}` used unquoted break on
  spaces, globs, and empty values. Nearly always should be `"$var"`.
- **Error handling**: is `set -euo pipefail` present at the top? Without it, a
  failing command mid-script is silently ignored and the script marches on. If
  it's intentionally absent, is failure checked explicitly?
- **`set -e` gotchas**: `cmd || true` swallows errors; a failing command in a
  `local x=$(cmd)` assignment doesn't trip `set -e` (the `local` masks the exit
  code). Watch for both.
- **Word splitting on command substitution**: `for f in $(ls)` is broken; prefer
  globs (`for f in *.txt`) or `while IFS= read -r line`.
- **`[ ]` vs `[[ ]]`**: unquoted `[ $x = y ]` fails on empty/multiword `$x`.
  Prefer `[[ ]]` for tests in bash.
- **Unvalidated input to destructive commands**: `rm -rf "$dir/"` when `$dir`
  could be empty → `rm -rf /`. Guard against empty/unset.
- **`cd` without checking**: `cd "$dir" && ...` or the script may run the rest in
  the wrong directory.
- **Pipelines & exit codes**: `a | b` returns b's status unless `pipefail`.
- **Portability**: `#!/bin/bash` vs `#!/bin/sh` — bashisms in an sh script break
  on dash. Match the shebang.
- Prefer `shellcheck` if available; most of the above are things it flags.

---

## Python

- **Exceptions**: bare `except:` or `except Exception: pass` swallows real
  errors. Is the caught scope as narrow as it should be? Is the error logged or
  re-raised?
- **Mutable default arguments**: `def f(x, items=[])` — the list is shared across
  calls. Classic bug.
- **Resource handling**: files/sockets opened without `with`; use context
  managers so they close on exceptions.
- **`subprocess`**: `shell=True` with any interpolated input is an injection
  risk — prefer a list argv. Check `check=True` (or the return code) so failures
  aren't ignored.
- **Path & string building**: use `pathlib`/`os.path.join` rather than f-string
  path concatenation that breaks cross-platform.
- **Truthiness traps**: `if x:` when `x` could legitimately be `0`, `""`, or an
  empty list but you meant `if x is not None:`.
- **Type/None flow**: a function that can return `None` whose caller assumes a
  value; missing `None` checks on dict `.get()`.
- **f-strings in logging / SQL**: log with `%`-args or structured logging;
  never build SQL by f-string (parameterize).
- **Imports**: unused imports, `import *`, importing heavy modules at top level
  for a rarely-used path.
- Prefer `ruff check` (style/bugs) and `bandit` (security) if installed.

---

## YAML & CI pipelines

Central to a Bitbucket→GitLab migration — much of the change surface is pipeline
config.

- **Validity**: indentation is consistent (spaces, not tabs); no duplicate keys
  (later silently wins); booleans/versions quoted where needed (`"3.10"` not
  `3.10`, the Norway problem: `no`/`yes`/`on`/`off` parse as booleans).
- **GitLab CI (`.gitlab-ci.yml`)**:
  - Each job has a valid `stage`; stages exist in `stages:`.
  - `rules:`/`only:`/`except:` logic — will the job run when intended and *not*
    run when it shouldn't? Watch for jobs that now run on every branch/MR.
  - `needs:` DAG references existing jobs; no cycles.
  - Secrets come from CI/CD variables (masked/protected), never inline.
  - `image:` tags pinned (avoid bare `latest` for reproducibility).
  - Caches/artifacts: correct `key`, `paths`, `expire_in`; not caching secrets.
- **Bitbucket Pipelines (`bitbucket-pipelines.yml`)** when reviewing pre-migration
  or comparing: `step`/`pipelines` structure, `caches`, `services`. When the MR
  *is* the migration, check the GitLab translation preserves the original
  behavior — same triggers, same steps, same env.
- **Migration-specific**: when a Bitbucket pipeline is being ported to GitLab CI,
  verify semantic equivalence, not just that it's valid YAML: same branches
  trigger it, same commands run in the same order, same artifacts/caches, secrets
  mapped to the new variable names.
- Prefer `yamllint` if installed.

---

## Dependencies

- **New dependencies**: is it necessary, or does the stdlib / an existing dep
  already cover it? Is it maintained and reputable?
- **Version pinning**: pinned appropriately (`requirements.txt` exact or
  compatible-release; no unpinned floating versions in production pipelines).
- **Known vulnerabilities**: flag obviously outdated/vulnerable versions if you
  recognize them; suggest `pip-audit`/`safety` if available.
- **Lockfile consistency**: if there's a lockfile, was it updated to match the
  manifest change?
- **Supply chain**: watch for typosquatted package names and packages pulled
  from non-standard indexes.

---

## Tests

- **Coverage of the change**: new logic and bug fixes come with tests. A bug fix
  with no test that would have caught the bug is a yellow flag — the bug can
  return.
- **Quality, not just presence**: do the tests assert on behavior/output, or do
  they just run the code and assert nothing meaningful? Do they cover the edge
  cases the change introduces?
- **Failure cases tested**, not only the happy path.
- **Determinism**: no reliance on wall-clock time, network, ordering, or shared
  mutable state that makes tests flaky.
- For shell, is there at least a smoke test / `bats` case? For pipelines, is
  there a way the change was validated (a dry-run, a test branch)?
