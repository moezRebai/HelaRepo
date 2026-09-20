# A. Vue d'ensemble & concepts

> Partie A du guide utilisateur Confluence — migration Bitbucket → GitLab/Ansible/AWX.
> Public : tous (opérateurs et développeurs). À lire en premier.

---

## 1. Introduction — pourquoi cette migration

Historiquement, les scripts d'automatisation (Bash/Python) vivaient dans des
dépôts **Bitbucket** et étaient déclenchés par des jobs **Jenkins** (freestyle
ou pipelines). Ce modèle pose plusieurs problèmes :

- **Idempotence non garantie** — un script Bash relancé deux fois peut échouer
  ou produire un état incohérent (ex. `apt-get install` sans vérification
  préalable, `systemctl restart` inconditionnel).
- **Pas de séparation code / configuration / secrets** — variables hardcodées
  ou lues depuis l'environnement, sans structure ni chiffrement natif.
- **Testabilité faible** — aucun test isolé, aucune vérification automatique
  de l'état final avant mise en production.
- **Deux outils à maintenir** — Bitbucket (SCM) + Jenkins (orchestration),
  avec une logique de déclenchement dispersée entre les deux.

**La cible retenue :**

- Le code d'automatisation est réécrit en **rôles et playbooks Ansible**,
  hébergés sur **GitLab** (SCM uniquement — GitLab CI ne fait que du
  lint/syntaxe, jamais d'exécution de playbook).
- **AWX** devient l'**orchestrateur unique** : il remplace entièrement
  Jenkins. Toute la configuration AWX (projects, inventories, credentials,
  job templates, schedules) est déclarée en YAML versionné
  (« config-as-code »), donc reproductible depuis le dépôt.
- Un **guide Confluence** (ce document) documente l'usage quotidien
  (opérateurs) et l'extension de la solution (développeurs).

Ce guide couvre la **tranche 1** de la migration : la catégorie
« automatisation serveur/infra », convertie de bout en bout (rôle
`webserver`, job template `webserver-provision`) et servant de gabarit pour
les tranches suivantes (déploiement/release, ops/maintenance, glue data/API).

---

## 2. Carte des composants

Le pipeline complet, de la source legacy jusqu'à la documentation, comprend
cinq briques :

```
SOURCE (faux repo)  --conversion-->  PROJET ANSIBLE  --héberge-->  GITLAB (SCM)
   Python/Bash                       roles/playbooks               |
                                     + tests + conf                | pull & exécute
                                                                   v
                              CONFLUENCE (guide)  <--documente--  AWX (orchestrateur unique)
```

1. **Source (factice)** — petit dépôt façon Bitbucket
   (`fake-source/infra-provisioning/`), avec `provision.sh` (installation
   paquet, création utilisateur, déploiement config, activation service) et
   `health_check.py` (vérification de port, logique procédurale).
2. **Projet Ansible** (`ansible-solution/`) — cible convertie : rôles,
   playbooks, inventaires, `ansible.cfg`, `requirements.yml`, tests
   Molecule. C'est le dépôt que ce guide documente.
3. **GitLab** — SCM **uniquement**. `.gitlab-ci.yml` exécute `ansible-lint`,
   `yamllint` et `--syntax-check` ; il ne lance **jamais** de playbook.
   AWX récupère le code depuis ce dépôt (Project SCM = GitLab).
4. **AWX** — orchestrateur **unique**, remplace Jenkins. Toute la
   configuration (`ansible-solution/awx/*.yml`) est appliquée via la
   collection `awx.awx` (playbook `awx/apply.yml`), donc reproductible.
5. **Confluence** — ce guide, en Markdown (source versionnée dans
   `docs/confluence/`) et en HTML « storage format » (prêt à coller/importer
   dans une page Confluence), publié manuellement (pas de connecteur API).

---

## 3. Glossaire

| Terme | Définition |
|-------|------------|
| **Job Template** | Objet AWX qui associe un playbook, un inventaire et des credentials ; c'est l'équivalent d'un job Jenkins (freestyle/pipeline). Exemple : `webserver-provision`. |
| **Workflow (Workflow Template)** | Enchaînement de plusieurs Job Templates avec logique succès/échec, équivalent d'un pipeline Jenkins chaîné. Non utilisé en tranche 1 (une seule étape). |
| **Inventory (inventaire)** | Liste des machines cibles et de leurs variables, organisée en groupes. Exemple : l'inventory AWX `dev` reflète `inventories/dev/hosts.yml` (groupe `webservers`, hôte `web1`). |
| **Role (rôle)** | Unité de conversion Ansible : une responsabilité fonctionnelle encapsulée (tâches, handlers, templates, valeurs par défaut, tests). Exemple : `roles/webserver/`. |
| **Vault (`ansible-vault`)** | Mécanisme de chiffrement natif Ansible pour les secrets (mots de passe, clés) stockés dans le dépôt (ex. `group_vars/vault.yml`). Complété par les Credentials AWX pour les valeurs injectées à l'exécution. |
| **Execution Environment (EE)** | Image (conteneur) dans laquelle AWX exécute un job : contient Ansible, les collections et les dépendances Python nécessaires (ex. `requests` pour un script glue encapsulé). |
| **Survey** | Formulaire affiché à AWX au lancement d'un Job Template, pour saisir des variables (ex. `app_port`). Équivalent des paramètres de build Jenkins. |
| **Credential (AWX)** | Identifiants chiffrés gérés par AWX (SSH machine, vault, API) et injectés au job sans jamais transiter par GitLab. Exemple : `dev-machine`. |
| **Schedule** | Planification native AWX (cron) pour déclencher un Job Template automatiquement. Exemple : `nightly-drift-check`. |
| **Project (AWX)** | Référence AWX vers le dépôt SCM (GitLab) contenant les playbooks/rôles ; synchronisé (pull) avant chaque lancement si `scm_update_on_launch: true`. Exemple : `ansible-solution`. |

**Suite du guide :**
- Partie B — [Guide opérateur](02-guide-operateur.md)
- Partie C — [Guide développeur](03-guide-developpeur.md)
- Partie D — [Référence & exploitation](04-reference-exploitation.md)
