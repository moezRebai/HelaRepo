# Plan d'implémentation — Tranche 1 (infra) : Bitbucket → GitLab/Ansible + AWX

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire passer un faux projet d'automatisation infra (Bash/Python) par toute la chaîne cible — conversion en role Ansible testé, dépôt GitLab (SCM), orchestration AWX config-as-code, et sections de guide Confluence — pour prouver la méthode de bout en bout.

**Architecture:** Approche B (tranche verticale puis réplication). Un role Ansible unique (`webserver`) porte la conversion ; Molecule/Docker prouve l'idempotence et l'état final ; un test d'équivalence compare le script original et le role ; AWX orchestre via config-as-code ; Confluence documente. GitLab n'est que SCM.

**Tech Stack:** Ansible (core ≥ 2.15), Molecule + `molecule-plugins[docker]`, Docker, `ansible-lint`, `yamllint`, collection `awx.awx`, `community.docker`. Python 3.10+ pour les scripts source factices et testinfra.

**Spec:** [docs/superpowers/specs/2026-09-18-migration-bitbucket-gitlab-ansible-awx-design.md](../specs/2026-09-18-migration-bitbucket-gitlab-ansible-awx-design.md)

## Global Constraints

- **Nœud de contrôle Linux requis** : Ansible/Molecule/Docker s'exécutent sous WSL2, conteneur ou VM Linux — jamais sur Windows natif. Toutes les commandes `Run:` supposent un shell Linux.
- **GitLab = SCM uniquement** : `.gitlab-ci.yml` ne fait que lint + `--syntax-check`, jamais `ansible-playbook` d'exécution réelle.
- **Secrets jamais en clair** : toute valeur sensible passe par `ansible-vault` (`inventories/*/group_vars/vault.yml`) ou les Credentials AWX. Aucun secret en dur dans les roles/playbooks/YAML AWX.
- **Idempotence obligatoire** : chaque role doit passer le test d'idempotence Molecule (2ᵉ `converge` = 0 changement).
- **Structure provisoire** : la disposition du dépôt est conforme au spec §3 en attendant les conventions Ansible de l'organisation ; ne pas inventer d'autre convention.
- **Nommage** : dépôt cible `ansible-solution/`, faux source `fake-source/infra-provisioning/`, role `webserver`.

---

## Cartographie des fichiers

**Faux source (entrée jetable, `fake-source/infra-provisioning/`)**
- `provision.sh` — script Bash à convertir : install paquets, déploie config, active service, crée user, gestion d'erreurs `set -e`.
- `health_check.py` — script Python idiome « glue » léger : appel HTTP local + code retour.
- `README.md` — décrit ce que le script est censé faire (l'intention à préserver).

**Dépôt cible (`ansible-solution/`)**
- `ansible.cfg` — `roles_path`, `inventory`, `host_key_checking=false`.
- `requirements.yml` — collections (`community.docker`, `awx.awx`).
- `.gitlab-ci.yml` — jobs `lint` + `syntax`.
- `.yamllint` — config yamllint.
- `inventories/dev/hosts.yml` — inventaire dev (conteneur cible).
- `inventories/dev/group_vars/all.yml` — vars non sensibles.
- `inventories/dev/group_vars/vault.yml` — secrets chiffrés (ex. contenu factice).
- `roles/webserver/{tasks,handlers,templates,defaults,meta}/…` — le role converti.
- `roles/webserver/molecule/default/{molecule.yml,converge.yml,verify.yml}` — tests.
- `playbooks/site.yml` — assemble le role sur le groupe cible.
- `awx/{projects,inventories,credentials,job_templates,schedules}.yml` — config-as-code.
- `awx/apply.yml` — playbook qui applique la config via `awx.awx`.
- `docs/conversion-catalog.md` — catalogue de correspondances (tranche 1).
- `docs/confluence/*.md` + `*.storage.html` — sections du guide.
- `tests/equivalence/{run_source.sh,run_role.sh,compare.sh}` — test d'équivalence.

---

## Task 1: Scaffolding du dépôt cible + garde-fous lint

**Files:**
- Create: `ansible-solution/ansible.cfg`
- Create: `ansible-solution/requirements.yml`
- Create: `ansible-solution/.yamllint`
- Create: `ansible-solution/.gitlab-ci.yml`
- Create: `ansible-solution/inventories/dev/hosts.yml`
- Create: `ansible-solution/inventories/dev/group_vars/all.yml`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces: dépôt lintable ; groupe d'inventaire `webservers` avec un hôte `web1` (conteneur Docker `connection: docker`) ; variable `app_port: 8080` dans `group_vars/all.yml`.

- [ ] **Step 1: Écrire la config projet**

`ansible-solution/ansible.cfg` :
```ini
[defaults]
inventory = inventories/dev/hosts.yml
roles_path = roles
host_key_checking = False
retry_files_enabled = False
stdout_callback = yaml
```

`ansible-solution/requirements.yml` :
```yaml
---
collections:
  - name: community.docker
    version: ">=3.4.0"
  - name: awx.awx
    version: ">=23.0.0"
```

`ansible-solution/.yamllint` :
```yaml
---
extends: default
rules:
  line-length:
    max: 160
  truthy:
    allowed-values: ["true", "false"]
  comments:
    min-spaces-from-content: 1
```

- [ ] **Step 2: Écrire l'inventaire dev + vars**

`ansible-solution/inventories/dev/hosts.yml` :
```yaml
---
all:
  children:
    webservers:
      hosts:
        web1:
          ansible_connection: docker
          ansible_host: web1
```

`ansible-solution/inventories/dev/group_vars/all.yml` :
```yaml
---
app_port: 8080
app_user: appsvc
web_package: nginx
```

- [ ] **Step 3: Écrire le pipeline GitLab (lint/syntaxe uniquement)**

`ansible-solution/.gitlab-ci.yml` :
```yaml
---
stages: [validate]

lint:
  stage: validate
  image: python:3.11
  script:
    - pip install ansible-lint yamllint "ansible-core>=2.15"
    - yamllint .
    - ansible-lint

syntax:
  stage: validate
  image: python:3.11
  script:
    - pip install "ansible-core>=2.15"
    - ansible-playbook playbooks/site.yml --syntax-check
```

- [ ] **Step 4: Vérifier que le lint passe sur le squelette**

Run (depuis `ansible-solution/`) :
```bash
pip install ansible-lint yamllint "ansible-core>=2.15"
yamllint .
```
Expected: PASS (aucune erreur yamllint). `ansible-lint` peut avertir de l'absence de playbooks — acceptable à ce stade, sera vert après Task 4.

- [ ] **Step 5: Commit**

```bash
git add ansible-solution/
git commit -m "chore: scaffold cible ansible-solution + garde-fous lint"
```

---

## Task 2: Construire le faux projet source infra (entrée jetable)

**Files:**
- Create: `fake-source/infra-provisioning/provision.sh`
- Create: `fake-source/infra-provisioning/health_check.py`
- Create: `fake-source/infra-provisioning/README.md`

**Interfaces:**
- Consumes: rien.
- Produces: script Bash `provision.sh` (idempotence NON garantie — volontaire) qui installe `nginx`, écrit `/etc/myapp/app.conf` avec un port, crée l'utilisateur `appsvc`, active le service, puis lance `health_check.py`. Ces idiomes sont la matière du catalogue (Task 6) et la référence du test d'équivalence (Task 5).

- [ ] **Step 1: Écrire le script Bash source**

`fake-source/infra-provisioning/provision.sh` :
```bash
#!/usr/bin/env bash
# Provisionne un serveur web — script Bitbucket "legacy" à convertir.
set -euo pipefail

APP_PORT="${APP_PORT:-8080}"
APP_USER="appsvc"

echo "[1/5] Installation nginx"
apt-get update -y
apt-get install -y nginx

echo "[2/5] Création utilisateur ${APP_USER}"
if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --no-create-home "${APP_USER}"
fi

echo "[3/5] Déploiement config"
mkdir -p /etc/myapp
cat > /etc/myapp/app.conf <<EOF
listen_port=${APP_PORT}
run_as=${APP_USER}
EOF

echo "[4/5] Activation service"
systemctl enable nginx
systemctl restart nginx

echo "[5/5] Health check"
python3 "$(dirname "$0")/health_check.py" "${APP_PORT}"
```

- [ ] **Step 2: Écrire le script Python "glue" (health check)**

`fake-source/infra-provisioning/health_check.py` :
```python
#!/usr/bin/env python3
"""Vérifie qu'un port répond. Idiome data/API glue (procédural)."""
import sys
import socket


def check(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ok = check(port)
    print(f"health: port {port} {'OK' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
```

- [ ] **Step 3: Documenter l'intention**

`fake-source/infra-provisioning/README.md` :
```markdown
# infra-provisioning (source legacy factice)

Provisionne un serveur web :
1. installe nginx
2. crée l'utilisateur système `appsvc`
3. écrit `/etc/myapp/app.conf` (port + utilisateur)
4. active et (re)démarre nginx
5. vérifie que le port répond (health_check.py)

Défauts volontaires (à corriger par la conversion) :
- non idempotent (`apt-get install`, `restart` systématique)
- config générée par heredoc, pas de gabarit
- health check procédural en Python (idiome "glue")
```

- [ ] **Step 4: Vérifier la syntaxe des scripts**

Run:
```bash
bash -n fake-source/infra-provisioning/provision.sh
python3 -m py_compile fake-source/infra-provisioning/health_check.py
```
Expected: PASS (aucune sortie d'erreur, code retour 0).

- [ ] **Step 5: Commit**

```bash
git add fake-source/
git commit -m "test: faux projet source infra (entrée de conversion)"
```

---

## Task 3: Convertir en role `webserver` (TDD via Molecule)

**Files:**
- Create: `ansible-solution/roles/webserver/defaults/main.yml`
- Create: `ansible-solution/roles/webserver/meta/main.yml`
- Create: `ansible-solution/roles/webserver/templates/app.conf.j2`
- Create: `ansible-solution/roles/webserver/handlers/main.yml`
- Create: `ansible-solution/roles/webserver/tasks/main.yml`
- Create: `ansible-solution/roles/webserver/molecule/default/molecule.yml`
- Create: `ansible-solution/roles/webserver/molecule/default/converge.yml`
- Create: `ansible-solution/roles/webserver/molecule/default/verify.yml`

**Interfaces:**
- Consumes: variables `app_port`, `app_user`, `web_package` (défaut dans le role, surchargeables par `group_vars`).
- Produces: role `webserver` idempotent qui installe `web_package`, crée `app_user`, déploie `/etc/myapp/app.conf` via gabarit, gère le service via handler `restart web`. Utilisé par `playbooks/site.yml` (Task 4).

- [ ] **Step 1: Écrire le scénario Molecule (le harnais de test)**

`ansible-solution/roles/webserver/molecule/default/molecule.yml` :
```yaml
---
driver:
  name: docker
platforms:
  - name: web-instance
    image: geerlingguy/docker-ubuntu2204-ansible:latest
    pre_build_image: true
    command: /lib/systemd/systemd
    privileged: true
    cgroupns_mode: host
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
provisioner:
  name: ansible
verifier:
  name: ansible
```

`ansible-solution/roles/webserver/molecule/default/converge.yml` :
```yaml
---
- name: Converge
  hosts: all
  become: true
  roles:
    - role: webserver
```

- [ ] **Step 2: Écrire les assertions `verify` (l'état final attendu)**

`ansible-solution/roles/webserver/molecule/default/verify.yml` :
```yaml
---
- name: Verify
  hosts: all
  become: true
  tasks:
    - name: Récupérer l'état du paquet nginx
      ansible.builtin.command: dpkg -s nginx
      register: pkg
      changed_when: false

    - name: Récupérer l'utilisateur appsvc
      ansible.builtin.getent:
        database: passwd
        key: appsvc

    - name: Lire la config déployée
      ansible.builtin.slurp:
        src: /etc/myapp/app.conf
      register: conf

    - name: Vérifier l'état final
      ansible.builtin.assert:
        that:
          - "'install ok installed' in pkg.stdout"
          - "'listen_port=8080' in (conf.content | b64decode)"
          - "'run_as=appsvc' in (conf.content | b64decode)"
        fail_msg: "État final incorrect après converge"
```

- [ ] **Step 3: Lancer Molecule pour vérifier l'échec (role vide)**

Run (depuis `ansible-solution/roles/webserver`) :
```bash
molecule test
```
Expected: FAIL — le role n'a pas de tâches, `verify` échoue (nginx absent / config absente).

- [ ] **Step 4: Écrire defaults, meta et gabarit**

`ansible-solution/roles/webserver/defaults/main.yml` :
```yaml
---
app_port: 8080
app_user: appsvc
web_package: nginx
```

`ansible-solution/roles/webserver/meta/main.yml` :
```yaml
---
galaxy_info:
  role_name: webserver
  description: Provisionne un serveur web (converti depuis provision.sh)
  license: MIT
  min_ansible_version: "2.15"
dependencies: []
```

`ansible-solution/roles/webserver/templates/app.conf.j2` :
```jinja
listen_port={{ app_port }}
run_as={{ app_user }}
```

- [ ] **Step 5: Écrire le handler**

`ansible-solution/roles/webserver/handlers/main.yml` :
```yaml
---
- name: restart web
  ansible.builtin.service:
    name: "{{ web_package }}"
    state: restarted
```

- [ ] **Step 6: Écrire les tâches du role (la conversion)**

`ansible-solution/roles/webserver/tasks/main.yml` :
```yaml
---
- name: Installer le paquet web
  ansible.builtin.apt:
    name: "{{ web_package }}"
    state: present
    update_cache: true

- name: Créer l'utilisateur système applicatif
  ansible.builtin.user:
    name: "{{ app_user }}"
    system: true
    create_home: false

- name: S'assurer que le répertoire de config existe
  ansible.builtin.file:
    path: /etc/myapp
    state: directory
    mode: "0755"

- name: Déployer la config applicative
  ansible.builtin.template:
    src: app.conf.j2
    dest: /etc/myapp/app.conf
    mode: "0644"
  notify: restart web

- name: Activer et démarrer le service web
  ansible.builtin.service:
    name: "{{ web_package }}"
    enabled: true
    state: started
```

- [ ] **Step 7: Lancer Molecule — converge, idempotence, verify**

Run (depuis `ansible-solution/roles/webserver`) :
```bash
molecule test
```
Expected: PASS sur toutes les étapes, **notamment l'idempotence** (le 2ᵉ converge rapporte `changed=0`) et `verify`.

- [ ] **Step 8: Commit**

```bash
git add ansible-solution/roles/webserver/
git commit -m "feat: role webserver converti depuis provision.sh (idempotent, testé Molecule)"
```

---

## Task 4: Playbook d'assemblage + validation syntaxe

**Files:**
- Create: `ansible-solution/playbooks/site.yml`

**Interfaces:**
- Consumes: role `webserver` (Task 3), groupe `webservers` (Task 1).
- Produces: `playbooks/site.yml` — point d'entrée exécuté par AWX (Task 7).

- [ ] **Step 1: Écrire le playbook**

`ansible-solution/playbooks/site.yml` :
```yaml
---
- name: Provisionner les serveurs web
  hosts: webservers
  become: true
  roles:
    - webserver
```

- [ ] **Step 2: Vérifier la syntaxe**

Run (depuis `ansible-solution/`) :
```bash
ansible-playbook playbooks/site.yml --syntax-check
```
Expected: PASS (`playbook: playbooks/site.yml`).

- [ ] **Step 3: Vérifier que ansible-lint est vert sur tout le dépôt**

Run (depuis `ansible-solution/`) :
```bash
ansible-lint
```
Expected: PASS (0 erreur). Corriger les avertissements bloquants s'il y en a.

- [ ] **Step 4: Commit**

```bash
git add ansible-solution/playbooks/site.yml
git commit -m "feat: playbook site.yml assemblant le role webserver"
```

---

## Task 5: Test d'équivalence source ↔ cible

**Files:**
- Create: `tests/equivalence/run_source.sh`
- Create: `tests/equivalence/run_role.sh`
- Create: `tests/equivalence/compare.sh`
- Create: `tests/equivalence/README.md`

**Interfaces:**
- Consumes: `fake-source/infra-provisioning/provision.sh` (Task 2), role `webserver` (Task 3).
- Produces: preuve documentée que le role produit le même état final que le script, plus l'idempotence.

- [ ] **Step 1: Écrire l'exécution du script source dans un conteneur**

`tests/equivalence/run_source.sh` :
```bash
#!/usr/bin/env bash
# Exécute le script legacy dans un conteneur et capture l'état final.
set -euo pipefail
CID=$(docker run -d --privileged geerlingguy/docker-ubuntu2204-ansible:latest /lib/systemd/systemd)
docker cp fake-source/infra-provisioning "$CID":/src
docker exec "$CID" bash -c "cd /src && APP_PORT=8080 bash provision.sh" || true
docker exec "$CID" bash -c "dpkg -s nginx | grep Status; getent passwd appsvc; cat /etc/myapp/app.conf" > /tmp/source_state.txt
docker rm -f "$CID" >/dev/null
echo "État source -> /tmp/source_state.txt"; cat /tmp/source_state.txt
```

- [ ] **Step 2: Écrire l'exécution du role dans un conteneur**

`tests/equivalence/run_role.sh` :
```bash
#!/usr/bin/env bash
# Exécute le role via un playbook éphémère et capture l'état final.
set -euo pipefail
CID=$(docker run -d --name eq-role --privileged geerlingguy/docker-ubuntu2204-ansible:latest /lib/systemd/systemd)
cat > /tmp/eq_inv.yml <<EOF
all:
  hosts:
    eq-role:
      ansible_connection: docker
EOF
ansible-playbook -i /tmp/eq_inv.yml ansible-solution/playbooks/site.yml
docker exec "$CID" bash -c "dpkg -s nginx | grep Status; getent passwd appsvc; cat /etc/myapp/app.conf" > /tmp/role_state.txt
docker rm -f "$CID" >/dev/null
echo "État role -> /tmp/role_state.txt"; cat /tmp/role_state.txt
```

- [ ] **Step 3: Écrire la comparaison**

`tests/equivalence/compare.sh` :
```bash
#!/usr/bin/env bash
set -euo pipefail
bash tests/equivalence/run_source.sh
bash tests/equivalence/run_role.sh
echo "=== DIFF source vs role ==="
if diff -u /tmp/source_state.txt /tmp/role_state.txt; then
  echo "ÉQUIVALENT : état final identique."
else
  echo "DIVERGENCE : voir diff ci-dessus."; exit 1
fi
```

- [ ] **Step 4: Lancer la comparaison**

Run (depuis la racine du dépôt) :
```bash
bash tests/equivalence/compare.sh
```
Expected: `ÉQUIVALENT : état final identique.` (paquet installé, user présent, config identique).

- [ ] **Step 5: Documenter et committer**

`tests/equivalence/README.md` : décrire l'objectif, comment lancer, et noter que le role ajoute l'idempotence que le script n'avait pas.
```bash
git add tests/equivalence/
git commit -m "test: équivalence source(provision.sh) <-> role webserver"
```

---

## Task 6: Catalogue de conversion (tranche 1)

**Files:**
- Create: `ansible-solution/docs/conversion-catalog.md`

**Interfaces:**
- Consumes: idiomes de `provision.sh`/`health_check.py` (Task 2), tâches du role (Task 3).
- Produces: table de correspondances réutilisée par le guide Confluence (Task 8, §8).

- [ ] **Step 1: Écrire le catalogue**

`ansible-solution/docs/conversion-catalog.md` — reprendre la table du spec §4 et y ajouter, pour chaque ligne, le pointeur vers la tâche concrète du role (`tasks/main.yml`) et une note idempotence. Inclure la **règle convertir vs encapsuler** : le health check Python reste un idiome « glue » qui, en tranche ultérieure, sera encapsulé (module custom / `ansible.builtin.uri`) plutôt que traduit tâche par tâche.

- [ ] **Step 2: Vérifier le rendu Markdown**

Run:
```bash
yamllint -d "{extends: relaxed, rules: {line-length: disable}}" ansible-solution/docs/conversion-catalog.md || true
```
Expected: pas d'erreur bloquante (contrôle léger ; le fichier est du Markdown).

- [ ] **Step 3: Commit**

```bash
git add ansible-solution/docs/conversion-catalog.md
git commit -m "docs: catalogue de conversion tranche 1 (infra)"
```

---

## Task 7: Orchestration AWX (config-as-code)

**Files:**
- Create: `ansible-solution/awx/projects.yml`
- Create: `ansible-solution/awx/inventories.yml`
- Create: `ansible-solution/awx/credentials.yml`
- Create: `ansible-solution/awx/job_templates.yml`
- Create: `ansible-solution/awx/schedules.yml`
- Create: `ansible-solution/awx/apply.yml`
- Create: `ansible-solution/awx/README.md`

**Interfaces:**
- Consumes: `playbooks/site.yml` (Task 4), inventaire (Task 1).
- Produces: définition AWX appliquable via `awx.awx` : Project (SCM=GitLab), Inventory, Credential (machine), Job Template `webserver-provision` + Survey (port), Schedule.

- [ ] **Step 1: Écrire les définitions d'objets AWX**

`ansible-solution/awx/projects.yml` :
```yaml
---
awx_projects:
  - name: ansible-solution
    scm_type: git
    scm_url: "{{ gitlab_repo_url }}"
    scm_branch: main
    scm_update_on_launch: true
```
`ansible-solution/awx/inventories.yml` :
```yaml
---
awx_inventories:
  - name: dev
    hosts:
      - name: web1
```
`ansible-solution/awx/credentials.yml` :
```yaml
---
# Valeurs injectées à l'exécution — jamais en clair ici.
awx_credentials:
  - name: dev-machine
    credential_type: Machine
    inputs:
      username: "{{ awx_ssh_user }}"
      ssh_key_data: "{{ awx_ssh_key }}"
```
`ansible-solution/awx/job_templates.yml` :
```yaml
---
awx_job_templates:
  - name: webserver-provision
    project: ansible-solution
    playbook: playbooks/site.yml
    inventory: dev
    credentials: [dev-machine]
    survey_enabled: true
    survey_spec:
      name: ""
      description: "Paramètres de provisioning"
      spec:
        - question_name: "Port applicatif"
          variable: app_port
          type: integer
          default: 8080
          required: true
```
`ansible-solution/awx/schedules.yml` :
```yaml
---
awx_schedules:
  - name: nightly-drift-check
    unified_job_template: webserver-provision
    rrule: "DTSTART:20260101T020000Z RRULE:FREQ=DAILY;INTERVAL=1"
```

- [ ] **Step 2: Écrire le playbook d'application**

`ansible-solution/awx/apply.yml` :
```yaml
---
- name: Appliquer la config AWX
  hosts: localhost
  connection: local
  gather_facts: false
  vars_files:
    - projects.yml
    - inventories.yml
    - credentials.yml
    - job_templates.yml
    - schedules.yml
  tasks:
    - name: Projects
      awx.awx.project:
        name: "{{ item.name }}"
        scm_type: "{{ item.scm_type }}"
        scm_url: "{{ item.scm_url }}"
        scm_branch: "{{ item.scm_branch }}"
        scm_update_on_launch: "{{ item.scm_update_on_launch }}"
      loop: "{{ awx_projects }}"

    - name: Job templates
      awx.awx.job_template:
        name: "{{ item.name }}"
        project: "{{ item.project }}"
        playbook: "{{ item.playbook }}"
        inventory: "{{ item.inventory }}"
        survey_enabled: "{{ item.survey_enabled }}"
        survey_spec: "{{ item.survey_spec }}"
      loop: "{{ awx_job_templates }}"
```

- [ ] **Step 3: Valider la syntaxe (dry-run si pas d'instance AWX)**

Run (depuis `ansible-solution/`) :
```bash
ansible-galaxy collection install awx.awx
ansible-playbook awx/apply.yml --syntax-check
```
Expected: PASS. **Si une instance AWX de test existe**, exporter `CONTROLLER_HOST/USERNAME/PASSWORD` et lancer `ansible-playbook awx/apply.yml` puis vérifier dans l'UI AWX que le Job Template `webserver-provision` existe. Sinon, documenter dans `awx/README.md` que l'application réelle est un prérequis d'exécution.

- [ ] **Step 4: Documenter et committer**

`ansible-solution/awx/README.md` : prérequis (instance AWX, variables `gitlab_repo_url`, `awx_ssh_user`, `awx_ssh_key` via vault/env), correspondance Jenkins→AWX (table du spec §5), commande d'application.
```bash
git add ansible-solution/awx/
git commit -m "feat: config-as-code AWX pour webserver-provision"
```

---

## Task 8: Guide utilisateur Confluence (sections tranche 1)

**Files:**
- Create: `ansible-solution/docs/confluence/01-vue-ensemble.md`
- Create: `ansible-solution/docs/confluence/02-guide-operateur.md`
- Create: `ansible-solution/docs/confluence/03-guide-developpeur.md`
- Create: `ansible-solution/docs/confluence/04-reference-exploitation.md`
- Create: `ansible-solution/docs/confluence/README.md`

**Interfaces:**
- Consumes: architecture (spec §2), structure (spec §3), catalogue (Task 6), AWX (Task 7).
- Produces: contenu Markdown des 4 parties du guide (spec §6), publiable manuellement.

- [ ] **Step 1: Écrire la Partie A — Vue d'ensemble & concepts**

`01-vue-ensemble.md` : introduction (pourquoi la migration), carte des composants (diagramme ASCII du spec §2), glossaire (Job Template, Workflow, Inventory, Role, Vault, Execution Environment).

- [ ] **Step 2: Écrire la Partie B — Guide opérateur**

`02-guide-operateur.md` : (3) se connecter à AWX & trouver `webserver-provision` ; (4) lancer un job — remplir le survey `app_port`, choisir l'inventaire `dev`, suivre l'exécution, lire les logs ; (5) planifications (`nightly-drift-check`) ; (6) dépannage (erreurs SSH, sync SCM, échec health check). Chaque étape numérotée, suivable sans connaissance préalable.

- [ ] **Step 3: Écrire la Partie C — Guide développeur**

`03-guide-developpeur.md` : (7) structure du dépôt (spec §3) ; (8) intégrer le catalogue de conversion (lien vers `conversion-catalog.md`) ; (9) règle convertir/encapsuler + ajouter un role et le tester avec Molecule (`molecule test`) ; (10) publier : commit GitLab → sync Project AWX → Job Template.

- [ ] **Step 4: Écrire la Partie D — Référence & exploitation**

`04-reference-exploitation.md` : (11) secrets (`ansible-vault` + Credentials AWX) ; (12) Execution Environments (dépendances Python des scripts glue) ; (13) checklist de migration d'un projet Bitbucket existant.

- [ ] **Step 5: Générer le format storage HTML de Confluence**

`README.md` documente la conversion. Générer les `.storage.html` à partir des `.md` :
```bash
for f in ansible-solution/docs/confluence/0*.md; do
  pandoc "$f" -f gfm -t html -o "${f%.md}.storage.html"
done
```
Expected: un `.storage.html` par page (si `pandoc` absent, documenter la commande comme prérequis dans `README.md` et livrer le Markdown seul).

- [ ] **Step 6: Commit**

```bash
git add ansible-solution/docs/confluence/
git commit -m "docs: guide utilisateur Confluence (sections tranche 1)"
```

---

## Auto-revue (couverture du spec)

- **Spec §2 (architecture)** → Task 1 (dépôt), Task 8 §1 (diagramme). ✔
- **Spec §3 (structure)** → Task 1 + arborescence des roles/awx/docs au fil des tâches. ✔
- **Spec §4 (tranche + catalogue)** → Task 2 (source infra en premier), Task 3 (conversion), Task 6 (catalogue). ✔
- **Spec §5 (AWX config-as-code)** → Task 7. ✔
- **Spec §6 (Confluence)** → Task 8. ✔
- **Spec §7 (tests : statique/Molecule/équivalence/AWX)** → Task 1 (lint), Task 3 (Molecule + idempotence), Task 5 (équivalence), Task 7 step 3 (AWX dry-run). ✔
- **Spec §8 (hypothèses)** → Global Constraints (Linux/WSL, Docker) + Task 7 (AWX optionnel). ✔
- **Glue data/API** → `health_check.py` (Task 2) traité comme cas « encapsuler » documenté (Task 6) ; conversion réelle en tranche ultérieure (hors périmètre de ce plan).
- **Cohérence des noms** : `webserver` (role), `webserver-provision` (job template), `app_port`/`app_user`/`web_package` (vars) — identiques partout. ✔
