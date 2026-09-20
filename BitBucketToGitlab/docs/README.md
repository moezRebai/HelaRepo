# Bitbucket → GitLab / Ansible / AWX Migration — Project Documentation

**Status:** Tranche 1 (infrastructure category) complete and validated.
**Audience:** Engineers and stakeholders new to this repository.
**Scope of this document:** What was built, why, how it fits together, how to run and extend it, and what comes next.

---

## 1. Purpose

This repository is a **reference implementation** for migrating legacy automation
projects off Bitbucket onto a modern, reproducible stack:

- **From:** projects hosted in Bitbucket, written in **Python / Bash**.
- **To:** a **GitLab-hosted Ansible project**, orchestrated **solely by AWX**
  (which replaces Jenkins entirely), documented by a **Confluence user guide**.

There was no real source code available at the start, so the project deliberately
builds **representative "fake" projects** to exercise and prove the migration
method end to end. The result is a working, tested blueprint plus a reusable
conversion catalog that later work can follow.

### Why AWX and not Jenkins

The original brief mentioned adjusting Jenkins jobs, but the decision taken was
**AWX as the sole orchestrator, no Jenkins at all**. Whatever the old Jenkins
jobs did is re-expressed as **AWX job templates** pulling from GitLab. This
removes a whole transitional subsystem and makes the target reproducible.

---

## 2. Approach: vertical slice first ("tranches")

The legacy scripts span **four categories**: (1) server/infra automation,
(2) app deployment/release, (3) ops/maintenance tasks, and (4) data/API glue.
Converting all four at once would be large and risky, so the work was decomposed
into **tranches** — one category taken all the way through the full toolchain
before replicating the proven pattern.

**Tranche 1 = the infrastructure category**, chosen first because it maps most
cleanly to native Ansible modules and exercises every link in the chain
(roles, inventory, idempotence, vault, AWX). The hardest category —
**data/API glue** — is deliberately left for last, because such procedural
logic is *encapsulated* (custom module / `ansible.builtin.uri` / `wait_for`)
rather than translated task-by-task.

This document covers **Tranche 1**. Later tranches (2: deployment, 3: ops,
4: glue) reuse the same structure and grow the conversion catalog and guide.

---

## 3. Architecture

The target is a **five-stage pipeline**; the vertical slice runs one fake
project through all of it:

```
 Bitbucket (legacy)   --conversion-->   Ansible project   --push (SCM)-->   GitLab
 Python / Bash                          role + playbook                     (SCM only)
                                                                               |
                                                                               | pull on launch
                                                                               v
 Confluence   <--documented (guide)--   AWX (sole orchestrator)   --runs playbook-->   Target servers
 user guide                             config-as-code                                 nginx + config + user
```

A rendered, interactive version of this diagram is at
[architecture/migration-tranche1.html](architecture/migration-tranche1.html).

**Boundary decisions:**

- **GitLab is SCM only.** No orchestration logic lives there; GitLab CI runs
  lint + syntax-check only, never a real playbook.
- **AWX config is version-controlled** (config-as-code), so the orchestration
  layer is reproducible from the repo rather than hand-clicked.
- **Secrets never live in the repo.** They flow through `ansible-vault` and
  AWX credentials, injected at run time.

---

## 4. Repository layout

```
BitBucketToGitlab/
├── fake-source/infra-provisioning/     # Throwaway legacy source (the INPUT)
│   ├── provision.sh                    # Bash provisioning script to convert
│   ├── health_check.py                 # Python "glue" idiom (TCP check)
│   └── README.md                       # Intent of the legacy script
│
├── ansible-solution/                   # The TARGET Ansible project (GitLab SCM)
│   ├── ansible.cfg
│   ├── requirements.yml                # Collections: community.docker, awx.awx
│   ├── .yamllint
│   ├── .gitlab-ci.yml                  # lint + syntax-check only (no execution)
│   ├── inventories/dev/
│   │   ├── hosts.yml                   # group `webservers`, host `web1`
│   │   └── group_vars/all.yml          # app_port / app_user / web_package
│   ├── roles/webserver/               # The converted role
│   │   ├── tasks/main.yml
│   │   ├── handlers/main.yml
│   │   ├── templates/app.conf.j2
│   │   ├── defaults/main.yml
│   │   ├── meta/main.yml
│   │   └── molecule/default/           # Molecule test scenario
│   │       ├── molecule.yml
│   │       ├── converge.yml
│   │       └── verify.yml
│   ├── playbooks/site.yml              # Entry-point playbook AWX runs
│   ├── awx/                            # AWX config-as-code
│   │   ├── projects.yml  inventories.yml  credentials.yml
│   │   ├── job_templates.yml  schedules.yml
│   │   ├── apply.yml                   # Applies the config via awx.awx
│   │   └── README.md
│   └── docs/
│       ├── conversion-catalog.md       # Bash/Python → Ansible mapping
│       └── confluence/                 # User guide (French, 4 parts)
│           ├── 01-vue-ensemble.md
│           ├── 02-guide-operateur.md
│           ├── 03-guide-developpeur.md
│           ├── 04-reference-exploitation.md
│           └── README.md
│
├── tests/equivalence/                  # Source-vs-role equivalence proof
│   ├── run_source.sh  run_role.sh  compare.sh  README.md
│
└── docs/                               # This documentation + design/plan
    ├── README.md                       # (this file)
    ├── architecture/migration-tranche1.html
    └── superpowers/                    # Design spec + implementation plan
```

---

## 5. Components in detail

### 5.1 Legacy source (`fake-source/infra-provisioning/`)

A deliberately **non-idempotent** Bash script representing a typical legacy
Bitbucket project. `provision.sh` installs nginx, creates a system user,
writes `/etc/myapp/app.conf` via a heredoc, enables/restarts the service, and
runs a Python health check. Its flaws (unconditional `apt-get install`,
`systemctl restart` every run, procedural Python) are intentional — they are
the material the conversion demonstrates value against.

### 5.2 Converted role (`ansible-solution/roles/webserver/`)

The role reproduces the script's *intent* with idempotent native modules:

| Legacy idiom | Ansible equivalent |
|---|---|
| `apt-get install -y nginx` | `ansible.builtin.apt` (state: present) |
| `useradd --system` (guarded) | `ansible.builtin.user` (system, no home) |
| heredoc → `/etc/myapp/app.conf` | `ansible.builtin.template` (`app.conf.j2`) |
| `systemctl enable/restart` | `ansible.builtin.service` + `notify: restart web` |
| hardcoded values | role vars `app_port` / `app_user` / `web_package` |

The restart is **notify-driven** (only on config change), which is the key
change that makes the role idempotent where the script was not. The full
mapping — with pointers into the role and the convert-vs-encapsulate rule —
lives in [../ansible-solution/docs/conversion-catalog.md](../ansible-solution/docs/conversion-catalog.md).

### 5.3 Playbook & inventory

`playbooks/site.yml` targets the `webservers` group and applies the `webserver`
role. `inventories/dev/` defines the `dev` environment. This playbook is the
entry point AWX executes.

### 5.4 AWX config-as-code (`ansible-solution/awx/`)

Everything AWX needs is declared in YAML and applied via `apply.yml` (using the
`awx.awx` collection), in dependency order:

```
Project → Inventory → Hosts → Credential → Job Template → Schedule
```

| Jenkins concept | AWX object (here) |
|---|---|
| Job / freestyle | **Job Template** `webserver-provision` (runs `site.yml`) |
| Build parameters | **Survey** (`app_port`) |
| Credentials | **Credential** `dev-machine` (SSH, values at run time) |
| Cron / trigger | **Schedule** `nightly-drift-check` |
| Repo of scripts | **Project** `ansible-solution` (SCM = GitLab) |

Secrets (`awx_ssh_user`, `awx_ssh_key`, `gitlab_repo_url`) are variable
references supplied at run time — never hardcoded. See
[../ansible-solution/awx/README.md](../ansible-solution/awx/README.md) for
prerequisites and the apply command.

### 5.5 Confluence user guide (`ansible-solution/docs/confluence/`)

A four-part guide (in French) for two audiences — operators and developers:

- **01 Vue d'ensemble** — introduction, component map, glossary.
- **02 Guide opérateur** — connect to AWX, launch `webserver-provision`, read
  logs, schedules, troubleshooting.
- **03 Guide développeur** — repo structure, conversion catalog, add/test a
  role with Molecule, publish flow (GitLab → AWX).
- **04 Référence & exploitation** — secrets, Execution Environments, migration
  checklist for an existing Bitbucket project.

Delivered as Markdown; the exact `pandoc` command to produce Confluence
storage-format HTML is documented in the guide's README (HTML not yet
generated — pandoc was unavailable in the build environment).

---

## 6. Validation & testing

The conversion is proven without production infrastructure, at three levels:

1. **Static (CI gate)** — `yamllint`, `ansible-lint`, and
   `ansible-playbook --syntax-check`, wired into `.gitlab-ci.yml`.
2. **Molecule (behavioral proof)** — the `webserver` role is deployed into a
   throwaway Docker container: `create → converge → idempotence → verify →
   destroy`. The **idempotence** stage (2nd converge = 0 changes) is the
   concrete proof of value over the legacy script. `verify.yml` asserts real
   final state (package installed, user present, config content).
3. **Equivalence (`tests/equivalence/`)** — runs the original `provision.sh`
   in one container and the role in another, then diffs the final state.
   Result: identical state, plus the role adds the idempotence the script
   lacked.

**Out of scope:** no tests run against real production; `prod` inventories are
templates, not executed.

---

## 7. How to run it

> **Environment note:** Ansible, Molecule, and Docker do **not** run on native
> Windows. Use WSL2 (a real Linux distro such as Ubuntu-24.04) or a Linux host,
> with Docker available. All commands below assume a Linux shell at the repo root.

**Install tooling and collections:**
```bash
pip install "ansible-core>=2.15" ansible-lint yamllint "molecule-plugins[docker]" molecule docker
cd ansible-solution && ansible-galaxy collection install -r requirements.yml
```

**Static checks (the CI gate):**
```bash
cd ansible-solution
yamllint .
ansible-playbook playbooks/site.yml --syntax-check
ansible-lint
```

**Behavioral test (Molecule):**
```bash
cd ansible-solution/roles/webserver
molecule test        # includes the idempotence stage
```

**Equivalence proof:**
```bash
bash tests/equivalence/compare.sh   # expects: "ÉQUIVALENT : état final identique."
```

**Apply AWX config (needs a live AWX instance + runtime vars):**
```bash
cd ansible-solution
ansible-playbook awx/apply.yml \
  -e gitlab_repo_url=<url> -e awx_ssh_user=<user> -e @<vault-with-ssh-key>
# Without an AWX instance, validate with: ansible-playbook awx/apply.yml --syntax-check
```

---

## 8. Key decisions

- **AWX is the sole orchestrator; Jenkins is removed entirely** (no transitional
  phase). Old Jenkins job behavior becomes AWX job templates.
- **GitLab is SCM only** — CI does lint/syntax-check, never real execution.
- **Vertical-slice first** — one category (infra) proven end to end, then
  replicated; this produces the reusable conversion catalog.
- **Convert vs encapsulate** — declarative work becomes Ansible tasks;
  procedural glue (e.g. `health_check.py`) is encapsulated rather than forced
  into YAML.
- **Shared, un-prefixed role vars** (`app_port`, etc.) are intentional so
  `group_vars` and role defaults stay coupled; `ansible-lint` flags this as a
  style warning (non-blocking, documented).

---

## 9. Known residuals & follow-ups

- Confluence `.storage.html` files are **not yet generated** (pandoc
  unavailable at build time); the guide ships as Markdown with the exact
  command documented.
- A few deferred lint/style items on the role (lowercase handler name, missing
  `author` in role meta, var-naming prefix) — cosmetic, non-blocking.
- Illustrative doc references (`vault/awx_secrets.yml`, `awx/workflows.yml`)
  are forward-looking examples, not current files.

---

## 10. What comes next (future tranches)

Each subsequent tranche reuses the proven pattern and enriches the conversion
catalog and the Confluence guide:

| Tranche | Category | Notes |
|---|---|---|
| 1 ✅ | Server/infra automation | This deliverable — the reference slice |
| 2 | App deployment / release | Playbooks + AWX job templates / workflow |
| 3 | Ops / maintenance | Playbooks + AWX schedules |
| 4 | Data/API glue | Hardest — encapsulate, don't translate line-by-line |

---

## 11. Reference documents

- **Design spec:** [superpowers/specs/2026-09-18-migration-bitbucket-gitlab-ansible-awx-design.md](superpowers/specs/2026-09-18-migration-bitbucket-gitlab-ansible-awx-design.md)
- **Implementation plan:** [superpowers/plans/2026-09-18-migration-tranche1-infra.md](superpowers/plans/2026-09-18-migration-tranche1-infra.md)
- **Architecture diagram:** [architecture/migration-tranche1.html](architecture/migration-tranche1.html)
- **Conversion catalog:** [../ansible-solution/docs/conversion-catalog.md](../ansible-solution/docs/conversion-catalog.md)
- **AWX config guide:** [../ansible-solution/awx/README.md](../ansible-solution/awx/README.md)
- **Confluence user guide (FR):** [../ansible-solution/docs/confluence/](../ansible-solution/docs/confluence/)
