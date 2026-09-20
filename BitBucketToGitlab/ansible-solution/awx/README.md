# Orchestration AWX (config-as-code)

AWX est l'orchestrateur unique de la solution : il remplace Jenkins pour le
lancement du provisioning (`playbooks/site.yml`). Rien ne se clique à la
main dans l'UI AWX — tout est déclaré ici en YAML versionné et appliqué via
la collection `awx.awx`, ce qui rend l'instance reproductible depuis le
dépôt (cf. spec §5).

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `projects.yml` | Project AWX (SCM = GitLab) qui pull `ansible-solution` |
| `inventories.yml` | Inventory `dev` + host `web1` |
| `credentials.yml` | Credential machine `dev-machine` (valeurs injectées à l'exécution) |
| `job_templates.yml` | Job Template `webserver-provision` (+ Survey `app_port`) |
| `schedules.yml` | Schedule `nightly-drift-check` |
| `apply.yml` | Playbook qui applique tous les objets ci-dessus dans l'ordre |

## Correspondance Jenkins → AWX (spec §5)

| Concept Jenkins        | Objet AWX                          | Rôle |
|------------------------|-------------------------------------|------|
| Job / freestyle        | **Job Template**                    | playbook + inventaire + credentials |
| Pipeline / job chaîné  | **Workflow Template**               | enchaînement succès/échec |
| Paramètres de build    | **Survey**                          | variables saisies au lancement |
| Credentials Jenkins    | **Credentials AWX**                 | SSH/vault/API, chiffrés, injectés |
| Cron / trigger         | **Schedule**                        | planification native |
| Agent / nœud           | **Inventory + Execution Environment** | où et dans quel contexte |
| Repo de scripts        | **Project** (SCM = GitLab)          | pull des playbooks depuis GitLab |

Dans cette tranche, seul le Job Template `webserver-provision` (équivalent
du job Jenkins historique) et son Schedule sont déclarés ; les Workflow
Templates et Execution Environments custom sont hors périmètre tranche 1
(voir spec §5, point de vigilance sur les dépendances Python des scripts
glue encapsulés).

## Prérequis

**Instance AWX/Controller cible :**
- `CONTROLLER_HOST` — URL de l'instance AWX
- `CONTROLLER_USERNAME` / `CONTROLLER_PASSWORD` (ou `CONTROLLER_OAUTH_TOKEN`) —
  identifiants avec droits de création d'objets

**Variables métier** (jamais en clair dans ce répertoire — à fournir via
Ansible Vault ou variables d'environnement au moment de l'apply) :
- `gitlab_repo_url` — URL du dépôt GitLab source (`projects.yml`)
- `awx_ssh_user` — utilisateur SSH du credential machine
- `awx_ssh_key` — clé privée SSH du credential machine (`ssh_key_data`)

Exemple (variables d'environnement, à préférer un vault chiffré en usage
réel) :

```bash
export CONTROLLER_HOST="https://awx.example.org"
export CONTROLLER_USERNAME="admin"
export CONTROLLER_PASSWORD="********"
```

Et via `-e`/vault pour les variables métier :

```bash
ansible-playbook awx/apply.yml \
  -e gitlab_repo_url="https://gitlab.example.org/infra/ansible-solution.git" \
  -e awx_ssh_user="deploy" \
  -e @vault/awx_secrets.yml   # contient awx_ssh_key, chiffré via ansible-vault
```

## Application

```bash
cd ansible-solution
ansible-galaxy collection install awx.awx
ansible-playbook awx/apply.yml --syntax-check   # validation hors ligne
ansible-playbook awx/apply.yml                  # application réelle (nécessite une instance AWX)
```

L'application réelle (`ansible-playbook awx/apply.yml` sans `--syntax-check`)
est un prérequis d'exécution : elle nécessite une instance AWX/Controller
joignable et les identifiants `CONTROLLER_*` ci-dessus. Aucune instance
n'étant disponible dans cet environnement de développement, seule la
validation syntaxique a été exécutée ici ; l'apply réel doit être rejoué
contre l'instance cible avant mise en service, puis vérifié dans l'UI AWX
(présence du Job Template `webserver-provision`, de l'inventory `dev`, du
credential `dev-machine` et du schedule `nightly-drift-check`).
