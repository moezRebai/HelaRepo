# Catalogue de conversion — Tranche 1 (infra)

**Date :** 2026-09-18  
**Périmètre :** Conversion du script Bash `provision.sh` (Bitbucket) et du health check Python `health_check.py` vers la solution Ansible cible.

---

## Introduction

Ce catalogue documente la correspondance entre les idiomes Bash/Python du script source et leurs équivalents Ansible dans le rôle converti `roles/webserver/`. Pour chaque idiome, nous indiquons :

1. **Idiome source** — code Bash ou Python original
2. **Équivalent Ansible** — module ou approche Ansible
3. **Pointeur concret** — tâche ou handler dans la role
4. **Note idempotence** — ce que la garantie Ansible améliore par rapport au script
5. **Classification** — **Convertir** (état déclaratif) vs **Encapsuler** (logique procédurale)

---

## Table de correspondances

### 1. Installation de paquets système

| Élément | Détail |
|---------|--------|
| **Idiome source** | `apt-get update -y` + `apt-get install -y nginx` |
| **Équivalent Ansible** | `ansible.builtin.apt` (name, state: present, update_cache) |
| **Pointeur concret** | `roles/webserver/tasks/main.yml` — tâche « Installer le paquet web » |
| **Note idempotence** | Le module `apt` est nativement idempotent : il ne réinstalle pas le paquet s'il est déjà présent. Le script source exécute `apt-get install` sans vérifier l'état, ce qui peut échouer en cas de seconde exécution (« paquet déjà installé »). |
| **Classification** | ✅ **Convertir** — déclarer l'état souhaité du paquet (présent) |

---

### 2. Création d'utilisateur système (avec test d'existence)

| Élément | Détail |
|---------|--------|
| **Idiome source** | `if ! id "${APP_USER}" >/dev/null 2>&1; then useradd --system --no-create-home "${APP_USER}"; fi` |
| **Équivalent Ansible** | `ansible.builtin.user` (name, system: true, create_home: false) |
| **Pointeur concret** | `roles/webserver/tasks/main.yml` — tâche « Créer l'utilisateur système applicatif » |
| **Note idempotence** | Le module `user` gère automatiquement le test d'existence et ne crée l'utilisateur que s'il n'existe pas. Aucun code conditionnel Bash ne cherche à vérifier l'état avant d'agir. La tâche Ansible est donc idempotente et déclarative. |
| **Classification** | ✅ **Convertir** — déclarer l'état souhaité de l'utilisateur (système, sans homedir) |

---

### 3. Création de répertoire avec permissions

| Élément | Détail |
|---------|--------|
| **Idiome source** | `mkdir -p /etc/myapp` |
| **Équivalent Ansible** | `ansible.builtin.file` (path, state: directory, mode) |
| **Pointeur concret** | `roles/webserver/tasks/main.yml` — tâche « S'assurer que le répertoire de config existe » |
| **Note idempotence** | Le module `file` avec `state: directory` est nativement idempotent : il ne crée le répertoire que s'il n'existe pas, et respecte le mode déclaré. L'option `-p` de `mkdir` empêche les erreurs si le répertoire existe déjà, mais n'applique pas de permissions idempotentes. |
| **Classification** | ✅ **Convertir** — déclarer l'état souhaité du répertoire (existant, mode 0755) |

---

### 4. Déploiement de fichier de configuration (cat > template)

| Élément | Détail |
|---------|--------|
| **Idiome source** | `cat > /etc/myapp/app.conf <<EOF ... listen_port=${APP_PORT} ... EOF` (substitution de variables par shell) |
| **Équivalent Ansible** | `ansible.builtin.template` (src: app.conf.j2, dest, mode) |
| **Pointeur concret** | `roles/webserver/tasks/main.yml` — tâche « Déployer la config applicative » ; fichier template `roles/webserver/templates/app.conf.j2` |
| **Note idempotence** | Le module `template` substitue les variables Jinja2 et n'écrit le fichier que si le contenu a changé (idempotent). Le script Bash écrit inconditionnellement le fichier à chaque exécution, écraser le fichier même s'il est identique. Ansible détecte le changement et n'écrit que si nécessaire. |
| **Classification** | ✅ **Convertir** — déclarer l'état souhaité du fichier (contenu et permissions) |

---

### 5. Gestion de services (enable + restart)

| Élément | Détail |
|---------|--------|
| **Idiome source** | `systemctl enable nginx` + `systemctl restart nginx` |
| **Équivalent Ansible** | `ansible.builtin.service` (name, enabled: true, state: started) ; handler `restart web` déclenché par `notify` sur changement |
| **Pointeur concret** | `roles/webserver/tasks/main.yml` — tâche « Activer et démarrer le service web » ; `roles/webserver/handlers/main.yml` — handler « restart web » |
| **Note idempotence** | Le module `service` avec `enabled: true` et `state: started` est idempotent : il ne redémarre le service que s'il a effectivement changé (via le handler `notify`). Le script Bash appelle `systemctl restart` inconditionnellement, ce qui relance le service même s'il est déjà correct. Le pattern Ansible avec handlers (notify/listen) garantit un redémarrage uniquement sur changement. |
| **Classification** | ✅ **Convertir** — déclarer l'état souhaité du service (activé au boot, démarré) |

---

### 6. Variables d'environnement et paramètres

| Élément | Détail |
|---------|--------|
| **Idiome source** | `APP_PORT="${APP_PORT:-8080}"` + `APP_USER="appsvc"` (variables d'env shell et hardcodées) |
| **Équivalent Ansible** | `defaults/main.yml` — variables de rôle déclarées (app_port, app_user, web_package) ; injéctées via `{{ variable }}` dans les tâches et templates |
| **Pointeur concret** | `roles/webserver/defaults/main.yml` — app_port: 8080, app_user: appsvc, web_package: nginx |
| **Note idempotence** | Le rôle Ansible externalise les paramètres dans `defaults/main.yml`, ce qui permet de les surcharger via `group_vars`, `host_vars`, ou au lancement du playbook. Le script Bash lit les variables d'env (env extern) ou les hardcode (mauvais), pas de surcharge structurée. Ansible garantit une séparation config/code. |
| **Classification** | ✅ **Convertir** — déclarer les paramètres comme variables de rôle (defaults) |

---

### 7. Gestion des erreurs et arrêt anticipé

| Élément | Détail |
|---------|--------|
| **Idiome source** | `set -euo pipefail` (exit on error, undefined vars, pipe fail) |
| **Équivalent Ansible** | Gestion implicite via statut de tâche (failed_when, block/rescue/always si nécessaire) |
| **Pointeur concret** | `roles/webserver/tasks/main.yml` — toutes les tâches héritent du comportement d'arrêt en cas d'erreur (par défaut, une tâche échouée arrête l'exécution) |
| **Note idempotence** | Ansible arrête l'exécution du playbook si une tâche échoue (comportement par défaut). Aucune configuration supplémentaire n'est nécessaire pour ce rôle simple. Pour des cas complexes (appel API, validation), `block/rescue/always` et `failed_when` permettent un contrôle fin. Le script Bash expose l'erreur au shell ; Ansible l'expose via le statut de playbook. |
| **Classification** | ✅ **Convertir** — gestion d'erreur implicite (rôle simple), bloc rescue si nécessaire |

---

### 8. Health check — vérification de port (Python procédural) ⚠️

| Élément | Détail |
|---------|--------|
| **Idiome source** | `python3 health_check.py "${APP_PORT}"` (socket TCP, vérification applicative) |
| **Équivalent Ansible (tranche 1)** | À **encapsuler** en tranche ultérieure |
| **Approche future** | `ansible.builtin.uri` (requête HTTP) OU `ansible.builtin.wait_for` (TCP socket) OU module custom en `library/` |
| **Pointeur concret** | Source : `fake-source/infra-provisioning/health_check.py` — logique procédurale (socket, timeout, exit code) |
| **Note idempotence** | Le health check est un **idiome glue/data** : logique procédurale (transformation de données, appels réseau, gestion d'état côté externe) non déclarative. La tranche 1 ne convertit PAS ce script tâche par tâche. En tranche ultérieure, on encapsulera via `ansible.builtin.wait_for` (pour TCP) ou un module custom si la logique devient complexe (ex. parsing JSON, chaîne d'appels API). Pour l'instant, ce cas est **documenté mais non implémenté** dans le rôle actuel. |
| **Classification** | ❌ **Encapsuler** — logique procédurale (appel réseau, vérification état applicatif), pas en tâches |

---

## Règle « Convertir vs Encapsuler »

### Convertir ✅
**Idiomes déclaratifs** : état système souhaité (paquet, utilisateur, fichier, service).

- Modules Ansible natifs : `apt`, `user`, `file`, `template`, `service`, `lineinfile`, etc.
- Résultat : tâches idempotentes, testables, traçables dans les logs.
- Exemple : « nginx doit être installé et le service activé au boot » → `apt` + `service`.

### Encapsuler ❌
**Idiomes procéduraux** : transformation de données, appels API chaînés, glue externe.

- Modules custom (Python) en `library/` → classe custom Ansible.
- Ou `ansible.builtin.script` / `ansible.builtin.command` → script en `files/`.
- Ou `ansible.builtin.uri` / `ansible.builtin.wait_for` si fourni nativement.
- **Jamais** forcé en YAML déclaratif.
- Exemple : health check TCP (socket Python) → `library/health_check.py` OU `wait_for` en tranche 2.

---

## Notes de tranche

- **Tranche 1 (actuelle)** : Convertir les idiomes déclaratifs (infra/serveur). Health check = documenté, encapsulation reportée.
- **Tranches ultérieures** : Encapsuler les glue scripts (API, data transforms) via `library/`, modules custom, ou appels AWS/HTTP. Enrichir le catalogue à chaque nouvelle catégorie.

---

## Correspondance détaillée du rôle

### Fichiers du rôle

```
roles/webserver/
├── tasks/main.yml          # 5 tâches déclaratives + 1 handler notify
├── handlers/main.yml       # 1 handler : restart service
├── templates/app.conf.j2   # Template Jinja2 de config
├── defaults/main.yml       # 3 variables : app_port, app_user, web_package
└── ...
```

### Tâches et correspondances

| # | Tâche (tasks/main.yml) | Idiome source | Module | Ligne src |
|---|------------------------|---------------|--------|-----------|
| 1 | Installer le paquet web | `apt-get install -y nginx` | `apt` | provision.sh:10 |
| 2 | Créer utilisateur système | `useradd --system` | `user` | provision.sh:14 |
| 3 | S'assurer répertoire config existe | `mkdir -p /etc/myapp` | `file` | provision.sh:18 |
| 4 | Déployer config applicative | `cat > app.conf <<EOF` | `template` + handler | provision.sh:19–22 |
| 5 | Activer et démarrer service | `systemctl enable` + `restart` | `service` | provision.sh:25–26 |
| — | Health check | `python3 health_check.py` | *(encapsuler tranche 2)* | provision.sh:29 |

---

## Résumé : gain d'idempotence

| Propriété | Script Bash | Ansible (rôle) |
|-----------|-----------|------------------|
| **Idempotence** | ❌ Partielle (test manuel via `if [ ! -f ]`, mais exécution inconditionnelle de certaines commandes) | ✅ Complète (modules natifs, handlers conditionnels, état déclaratif) |
| **Tracabilité** | ✅ Logs shell (stdout/stderr) | ✅ Logs Ansible structurés (changed, status, détails de tâche) |
| **Testabilité** | ❌ Difficile (aucun test isolé) | ✅ Facile (Molecule : test d'idempotence, verify état final) |
| **Surcharge de paramètres** | ❌ Via env (non structuré) ou hardcoding | ✅ Via defaults, group_vars, host_vars, survey AWX |
| **Gestion d'erreurs** | ✅ Explicite (`set -euo pipefail`) | ✅ Implicite (arrêt sur erreur par défaut) ; optionnel (block/rescue) |
| **Réutilisabilité** | ❌ Monolithique | ✅ Rôle réutilisable, paramétrable |

---

## Prochaines étapes (tranches suivantes)

1. **Tranche 2** : Catégorie déploiement/release (playbooks multi-environnement, vault, secrets).
2. **Tranche 3** : Catégorie ops/maintenance (planifications AWX, workflows).
3. **Tranche 4** : Catégorie glue/data (health check → `wait_for` ou module custom, appels API → modules custom ou `uri`).

À chaque tranche, ce catalogue sera enrichi avec de nouveaux idioms et patterns.
