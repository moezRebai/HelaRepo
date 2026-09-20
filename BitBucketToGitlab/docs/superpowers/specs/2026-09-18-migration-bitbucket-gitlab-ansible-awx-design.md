# Conception — Migration Bitbucket → GitLab/Ansible orchestré par AWX

**Date :** 2026-09-18
**Statut :** Validé en brainstorming, en attente de revue finale
**Approche retenue :** B — Tranche verticale de bout en bout, puis réplication (catalogue de patterns)

---

## 1. Contexte & objectif

Migrer des projets hébergés sur Bitbucket et écrits en **Python/Bash** vers un
**projet Ansible hébergé sur GitLab**, orchestré exclusivement par **AWX** (qui
remplace entièrement Jenkins), et documenté par un **guide utilisateur Confluence**.

**Nature du travail :** conception générique + implémentation de référence. Il
n'existe pas de source réelle disponible ; on construit des **projets factices**
représentatifs pour exercer et prouver la méthode. Les conventions Ansible de
l'organisation seront fournies ultérieurement et la structure cible y sera conformée.

**Catégories de scripts source à couvrir** (les quatre) :
1. Automatisation serveur/infra — mapping propre vers modules Ansible.
2. Déploiement / release applicatif — playbooks + job templates AWX.
3. Tâches ops/maintenance — playbooks + planifications AWX.
4. Glue data/API — **cas difficile** : encapsulé (module custom / `script`), pas forcé en YAML.

**Décision de périmètre importante :** l'exigence initiale « ajuster les jobs
Jenkins pour appeler la nouvelle solution » est **abandonnée**. Choix retenu :
AWX est l'orchestrateur **unique**, sans Jenkins du tout. Ce que faisaient les
jobs Jenkins est ré-exprimé en job templates AWX. (À rouvrir uniquement si une
phase transitoire Jenkins s'avère nécessaire.)

---

## 2. Architecture globale

Pipeline en cinq étapes ; la tranche verticale fait passer un faux projet par toutes :

```
SOURCE (faux repo)  --conversion-->  PROJET ANSIBLE  --héberge-->  GITLAB (SCM)
   Python/Bash                       roles/playbooks               |
                                     + tests + conf                | pull & exécute
                                                                   v
                              CONFLUENCE (guide)  <--documente--  AWX (orchestrateur unique)
```

1. **Source (factice)** — petit dépôt façon Bitbucket, entrée jetable, truffée
   volontairement des idiomes à convertir (boucle, condition, install paquet,
   appel API, gestion d'erreurs).
2. **Projet Ansible** — cible convertie : roles, playbooks, inventaires,
   `ansible.cfg`, `requirements.yml`, tests de roles. Conforme aux conventions org.
3. **GitLab** — SCM **uniquement**. GitLab CI ne fait que lint/syntaxe, aucune
   exécution de playbook. AWX récupère la source ici.
4. **AWX** — orchestrateur **unique**, remplace Jenkins. Défini en config-as-code
   (projects, inventories, credentials, job templates, schedules), reproductible.
5. **Confluence** — guide utilisateur en Markdown + HTML storage-format, publié
   manuellement (pas de connecteur API autorisé).

**Frontières clés :** GitLab = SCM sans logique d'orchestration ; config AWX
versionnée ; toute la cible reproductible depuis le dépôt.

---

## 3. Structure du dépôt cible (provisoire — à conformer aux conventions org)

```
ansible-<solution>/
├── ansible.cfg                      # roles_path, inventory, etc.
├── requirements.yml                 # collections + roles (ansible-galaxy)
├── .gitlab-ci.yml                   # lint/syntaxe uniquement — PAS d'exécution
│
├── inventories/
│   ├── dev/{hosts.yml, group_vars/{all.yml, vault.yml}}
│   └── prod/{hosts.yml, group_vars/}
│
├── playbooks/
│   ├── site.yml                     # orchestration principale
│   └── <tache>.yml                  # un playbook par cas d'usage
│
├── roles/
│   └── <role>/                      # une responsabilité = un role
│       ├── tasks/main.yml   handlers/main.yml   templates/
│       ├── defaults/main.yml   vars/main.yml    meta/main.yml
│       └── molecule/default/        # tests de role
│
├── library/                         # modules custom / scripts glue encapsulés
│   └── <script>.py
│
├── files/ & templates/
│
├── awx/                             # config-as-code AWX (voir §5)
│
└── docs/
    ├── confluence/                  # guide utilisateur (Markdown + HTML storage)
    └── conversion-catalog.md        # catalogue de correspondances
```

**Décisions structurantes :**
- `roles/` = unité de conversion (une responsabilité, testable en isolation).
- `library/` pour l'irréductible : scripts glue encapsulés comme modules custom
  ou appelés via `command`/`script`, jamais forcés en YAML.
- Séparation stricte code / secrets / inventaire : secrets en `vault.yml`
  (chiffré), config d'environnement en `group_vars/`, credentials injectés par AWX.

---

## 4. Tranche verticale & méthode de conversion

**Ordre des catégories :** infra/serveur **en premier** (mapping le plus propre,
exerce toute la chaîne, sert de gabarit) ; **glue data/API en dernier** (cas le
plus difficile, attaqué une fois la mécanique rodée).

**Faux projet source (tranche 1) :** configure un serveur — installe des paquets,
déploie un fichier de config, active un service, crée un utilisateur, vérification
de santé avec gestion d'erreurs.

**Catalogue de correspondances** (livrable réutilisable, grossit à chaque tranche) :

| Idiome source (Bash/Python)   | Équivalent Ansible                | Note |
|-------------------------------|-----------------------------------|------|
| `apt-get install -y nginx`    | module `ansible.builtin.apt`      | idempotent nativement |
| `if [ ! -f x ]; then …`       | `creates:` / `stat` + `when:`     | plus de test manuel |
| boucle `for h in hosts`       | inventaire + `hosts:`             | la boucle disparaît |
| `systemctl restart`           | `service` + `handlers` (`notify`) | déclenché sur changement |
| `sed -i` sur un fichier       | `lineinfile` / `template`         | gabarit Jinja2 préféré |
| `requests.get(api)` (Python)  | `ansible.builtin.uri`             | ou module custom si complexe |
| `set -e` / gestion d'erreur   | `block/rescue/always` + `failed_when` | |
| secrets en dur                | `ansible-vault` + `group_vars`    | injecté par AWX |

**Règle « convertir vs encapsuler » :**
- **Convertir** en tâches/role si déclaratif (état système souhaité).
- **Encapsuler** (module custom `library/` ou `script`/`command`) si procédural
  (transformation de données, appels API chaînés).

---

## 5. Orchestration AWX (config-as-code)

Rien ne se clique à la main : tout est déclaré en YAML versionné et appliqué via
la collection `awx.awx`. Instance reproductible depuis le dépôt.

**Correspondance des objets :**

| Concept Jenkins        | Objet AWX                          | Rôle |
|------------------------|------------------------------------|------|
| Job / freestyle        | **Job Template**                   | playbook + inventaire + credentials |
| Pipeline / job chaîné  | **Workflow Template**              | enchaînement succès/échec |
| Paramètres de build    | **Survey**                         | variables saisies au lancement |
| Credentials Jenkins    | **Credentials AWX**                | SSH/vault/API, chiffrés, injectés |
| Cron / trigger         | **Schedule**                       | planification native |
| Agent / nœud           | **Inventory + Execution Environment** | où et dans quel contexte |
| Repo de scripts        | **Project** (SCM = GitLab)         | pull des playbooks depuis GitLab |

**Répertoire `awx/` :** `projects.yml`, `inventories.yml`, `credentials.yml`
(valeurs via vault, jamais en clair), `job_templates.yml` (+ survey),
`workflows.yml`, `schedules.yml`.

**Flux d'exécution :** AWX pull depuis GitLab (sync au lancement) → lance le Job
Template → injecte les credentials → exécute dans un Execution Environment →
journalise. Les secrets ne transitent jamais par GitLab.

**Point de vigilance :** les scripts glue encapsulés peuvent nécessiter des
dépendances Python (ex. `requests`) présentes dans l'Execution Environment —
EE custom si besoin, documenté comme prérequis.

---

## 6. Guide utilisateur Confluence

Dans `docs/confluence/`, en Markdown (source versionnée) + HTML storage-format
(prêt à importer). Deux publics : opérateurs (usage quotidien) et développeurs
(faire évoluer la solution).

- **A. Vue d'ensemble & concepts** — 1. Introduction + carte des composants ;
  2. Glossaire.
- **B. Guide opérateur** — 3. Connexion AWX & trouver un job template ;
  4. Lancer un job (survey, inventaire, logs) ; 5. Planifications & workflows ;
  6. Dépannage.
- **C. Guide développeur** — 7. Structure du dépôt ; 8. **Catalogue de conversion**
  (pièce de référence) ; 9. Règle convertir/encapsuler + ajouter/tester un role
  (Molecule) ; 10. Publier un projet : GitLab → Job Template AWX.
- **D. Référence & exploitation** — 11. Gestion des secrets (vault + credentials
  AWX) ; 12. Execution Environments ; 13. Checklist de migration d'un projet
  Bitbucket existant.

Chaque procédure opérateur est pas-à-pas, suivable sans connaissance préalable.

---

## 7. Stratégie de test & validation

Prouver la conversion sans infrastructure réelle, par niveaux :

1. **Statique** — `ansible-lint`, `yamllint`, `--syntax-check` (dans GitLab CI).
2. **Molecule par role** — déploiement dans conteneur Docker jetable ;
   `create → converge → idempotence → verify → destroy`. Le test **d'idempotence**
   est central (démonstration concrète de la valeur vs script Bash original).
   `verify` assert l'état final (paquet, service, fichier).
3. **Équivalence source ↔ cible** — exécuter le script Bash original et le role
   Ansible dans deux conteneurs, comparer l'état final ; documenté dans le catalogue.
4. **AWX** — idéalement instance de test (`awx-operator`/Docker) : appliquer la
   config-as-code, lancer le job template contre l'inventaire conteneurisé. À
   défaut : validation de config en dry-run + revue manuelle (prérequis documenté).

**Hors périmètre :** aucun test contre la vraie prod ; inventaires `prod` = gabarits non exécutés.

---

## 8. Hypothèses & questions ouvertes

- **Conventions Ansible org** — à fournir ; la structure §3 y sera conformée.
- **Docker local** — supposé disponible pour Molecule (à confirmer).
- **Instance AWX de test** — optionnelle ; sinon config AWX validée en dry-run + revue.
- **Confluence** — pas de connecteur API autorisé ; livraison manuelle du contenu.
- **Périmètre Jenkins** — supprimé entièrement (pas de phase transitoire), sauf indication contraire.

---

## 9. Séquencement (livraison)

1. Faux projet source infra + dépôt cible squelette (conforme conventions org).
2. Conversion tranche 1 (role infra) + tests Molecule + catalogue initial.
3. Config-as-code AWX pour la tranche 1 + validation orchestration.
4. Guide Confluence : squelette + sections opérateur/développeur de la tranche 1.
5. Réplication des catégories restantes (déploiement, ops, **glue en dernier**),
   enrichissant catalogue + guide à chaque tranche.
