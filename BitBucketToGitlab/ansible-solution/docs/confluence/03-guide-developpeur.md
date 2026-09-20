# C. Guide développeur

> Partie C du guide utilisateur Confluence — faire évoluer la solution.
> Public : développeurs qui ajoutent des rôles, convertissent de nouveaux
> scripts, ou publient des changements.

---

## 7. Structure du dépôt

Le dépôt `ansible-solution/` suit la structure suivante (provisoire — à
conformer aux conventions Ansible de l'organisation lorsqu'elles seront
fournies) :

```
ansible-solution/
├── ansible.cfg                      # roles_path, inventory par défaut, etc.
├── requirements.yml                 # collections (community.docker, awx.awx)
├── .gitlab-ci.yml                   # lint/syntaxe uniquement — PAS d'exécution
│
├── inventories/
│   └── dev/
│       ├── hosts.yml                 # groupe webservers, hôte web1
│       └── group_vars/all.yml        # app_port, app_user, web_package
│
├── playbooks/
│   └── site.yml                      # orchestration principale (rôle webserver)
│
├── roles/
│   └── webserver/                    # rôle converti (tranche 1)
│       ├── tasks/main.yml
│       ├── handlers/main.yml
│       ├── templates/app.conf.j2
│       ├── defaults/main.yml
│       ├── meta/main.yml
│       └── molecule/default/         # tests Molecule (create/converge/verify/destroy)
│
├── awx/                              # config-as-code AWX (voir Partie D et awx/README.md)
│   ├── projects.yml
│   ├── inventories.yml
│   ├── credentials.yml
│   ├── job_templates.yml
│   ├── schedules.yml
│   └── apply.yml
│
└── docs/
    ├── confluence/                   # ce guide (Markdown + HTML storage)
    └── conversion-catalog.md         # catalogue de correspondances
```

**Principes structurants :**
- `roles/` est l'**unité de conversion** : une responsabilité fonctionnelle,
  testable en isolation via Molecule.
- `library/` (à créer lors de la tranche glue data/API) accueillera les
  scripts glue encapsulés (modules custom ou appelés via
  `command`/`script`), jamais forcés en YAML déclaratif.
- Séparation stricte code / secrets / inventaire : secrets dans
  `group_vars/vault.yml` (chiffré, à créer dès qu'un secret réel apparaît),
  configuration d'environnement dans `group_vars/`, credentials injectés
  par AWX à l'exécution (jamais en clair dans le dépôt).

---

## 8. Intégrer le catalogue de conversion

Le [catalogue de conversion](../conversion-catalog.md) est la pièce de
référence pour toute nouvelle conversion : pour chaque idiome Bash/Python
rencontré dans un script source, il documente l'équivalent Ansible, un
pointeur concret vers la tâche/rôle correspondant, une note sur le gain
d'idempotence, et une classification **Convertir** vs **Encapsuler**
(voir §9 ci-dessous).

**Quand convertir un nouveau script :**
1. Lire le catalogue existant pour repérer si l'idiome rencontré a déjà une
   correspondance documentée (ex. installation de paquet → `apt`, boucle
   sur hôtes → inventaire, `sed`/template → `template`/`lineinfile`).
2. Si l'idiome est nouveau, l'ajouter au catalogue en suivant le même
   format (idiome source, équivalent Ansible, pointeur, note idempotence,
   classification).
3. Le catalogue grossit à chaque tranche — il devient la documentation
   vivante de la méthode de conversion pour l'ensemble de l'organisation.

---

## 9. Règle « Convertir vs Encapsuler » — ajouter et tester un rôle

### La règle

- **Convertir** ✅ en tâches/rôle Ansible natif quand l'idiome est
  **déclaratif** (état système souhaité) : installation de paquet, création
  d'utilisateur/fichier/répertoire, gestion de service. Utiliser les
  modules natifs (`apt`, `user`, `file`, `template`, `service`, etc.).
- **Encapsuler** ❌ (module custom dans `library/`, ou `ansible.builtin.script`
  / `ansible.builtin.command`, ou `uri`/`wait_for` si applicable) quand
  l'idiome est **procédural** : transformation de données, appels API
  chaînés, logique métier complexe. Ne **jamais** forcer ce type de logique
  en YAML déclaratif.
- Exemple concret dans ce dépôt : le health check TCP (`health_check.py`,
  logique socket procédurale) est documenté comme cas « encapsuler » dans
  le catalogue, et sera traité en tranche ultérieure via
  `ansible.builtin.wait_for` ou un module custom — pas en tranche 1.

### Ajouter un nouveau rôle

1. Créer l'arborescence sous `roles/<nom-du-role>/` en suivant le même
   gabarit que `roles/webserver/` : `tasks/main.yml`, `handlers/main.yml`,
   `defaults/main.yml`, `vars/main.yml` (si besoin), `meta/main.yml`,
   `templates/` (si besoin).
2. Écrire les tâches en respectant la règle Convertir/Encapsuler ci-dessus.
3. Déclarer les paramètres du rôle dans `defaults/main.yml` (jamais de
   valeurs hardcodées dans les tâches).
4. Ajouter un scénario Molecule : `roles/<nom-du-role>/molecule/default/`
   avec `molecule.yml` (driver Docker, image de test), `converge.yml`
   (applique le rôle) et `verify.yml` (assertions sur l'état final :
   paquet installé, fichier déployé, service actif...).

### Tester avec Molecule

Depuis la racine du dépôt (ou depuis le rôle), avec Docker disponible :

```bash
cd ansible-solution
pip install molecule molecule-plugins[docker]
cd roles/<nom-du-role>
molecule test
```

`molecule test` enchaîne automatiquement : `create` (conteneur Docker
jetable) → `converge` (applique le rôle) → **`idempotence`** (relance le
rôle une seconde fois — doit produire **zéro** changement, c'est la preuve
concrète de la valeur du rôle Ansible par rapport au script Bash
original) → `verify` (assertions sur l'état final) → `destroy`. Le test
d'idempotence est le point le plus important : il matérialise la garantie
qu'un script Bash classique n'offre pas nativement.

Pour rejouer une étape isolément pendant le développement :
```bash
molecule converge   # applique sans détruire le conteneur, itératif
molecule verify     # relance uniquement les assertions
molecule destroy    # nettoie le conteneur de test
```

---

## 10. Publier : GitLab → sync Project AWX → Job Template

1. **Commit et push** vers le dépôt GitLab (`ansible-solution`, branche
   principale). Le pipeline `.gitlab-ci.yml` s'exécute automatiquement et
   valide `ansible-lint`, `yamllint` et `--syntax-check` — **aucune
   exécution de playbook** n'a lieu côté GitLab CI (GitLab est un SCM pur).
2. **Synchronisation du Project AWX** : le Project AWX `ansible-solution`
   (déclaré dans `awx/projects.yml`, pointant vers `scm_url:
   {{ gitlab_repo_url }}`, branche `main`) est configuré avec
   `scm_update_on_launch: true` — il se synchronise automatiquement à
   chaque lancement de Job Template. Un sync manuel est possible depuis
   l'UI AWX (**Projects** → `ansible-solution` → icône de synchronisation),
   ou en cas de modification de la configuration AWX elle-même
   (`awx/*.yml`), en rejouant :
   ```bash
   ansible-playbook awx/apply.yml
   ```
   (nécessite les variables `CONTROLLER_HOST`/`CONTROLLER_USERNAME`/
   `CONTROLLER_PASSWORD` et les secrets métier — voir `awx/README.md` et
   Partie D §11).
3. **Le Job Template récupère le nouveau code** : dès que le Project a
   synchronisé la nouvelle révision, tout lancement du Job Template
   `webserver-provision` (manuel ou via le schedule
   `nightly-drift-check`) exécute la version à jour de `playbooks/site.yml`
   et des rôles associés.
4. **Ajouter un nouveau Job Template** pour un nouveau playbook/rôle : le
   déclarer dans `awx/job_templates.yml` (nom, project, playbook,
   inventory, credentials, survey éventuel), puis rejouer
   `ansible-playbook awx/apply.yml` — jamais de création manuelle dans
   l'UI AWX (elle serait écrasée/désynchronisée du dépôt).

**Suite du guide :**
- Partie A — [Vue d'ensemble & concepts](01-vue-ensemble.md)
- Partie B — [Guide opérateur](02-guide-operateur.md)
- Partie D — [Référence & exploitation](04-reference-exploitation.md)
- [Catalogue de conversion](../conversion-catalog.md)
