# B. Guide opérateur

> Partie B du guide utilisateur Confluence — usage quotidien d'AWX.
> Public : opérateurs. Chaque procédure est numérotée et suivable sans
> connaissance préalable d'Ansible ou d'AWX.

Voir le [Glossaire](01-vue-ensemble.md#3-glossaire) pour les termes AWX
utilisés ci-dessous (Job Template, Survey, Inventory, Schedule...).

---

## 3. Se connecter à AWX et trouver le Job Template `webserver-provision`

1. Ouvrir un navigateur sur l'URL de l'instance AWX/Controller fournie par
   votre administrateur (ex. `https://awx.example.org`).
2. Se connecter avec vos identifiants AWX (utilisateur + mot de passe, ou
   SSO si configuré).
3. Dans le menu de gauche, cliquer sur **Templates**.
4. Dans la liste, repérer le Job Template nommé **`webserver-provision`**
   (type : Job Template, pas Workflow). C'est l'équivalent du job Jenkins
   historique de provisioning serveur web.
5. Cliquer sur son nom pour ouvrir sa fiche détail : vous y verrez le
   playbook associé (`playbooks/site.yml`), l'inventaire (`dev`) et le
   credential (`dev-machine`) déjà configurés — rien à modifier ici pour un
   lancement standard.

> Si `webserver-provision` n'apparaît pas dans la liste, vérifiez avec un
> développeur que la configuration AWX (`ansible-solution/awx/`) a bien été
> appliquée (voir Partie C, §10 « Publier »).

---

## 4. Lancer un job

1. Depuis la fiche du Job Template `webserver-provision` (voir étape 3),
   cliquer sur le bouton **Launch** (icône fusée, en haut à droite).
2. AWX affiche le **Survey** (formulaire de lancement). Un seul champ est
   demandé :
   - **Port applicatif** (variable `app_port`) — port sur lequel
     l'application web doit écouter. Valeur par défaut : `8080`. Laissez la
     valeur par défaut sauf instruction contraire.
3. Cliquer sur **Next**, puis vérifier l'écran de résumé :
   - **Inventory** doit afficher **`dev`** (l'inventaire de développement,
     hôte `web1`). Ne changez pas d'inventaire sauf instruction explicite —
     l'inventaire `prod` (s'il existe) n'est qu'un gabarit non exécuté.
   - **Credentials** doit afficher **`dev-machine`**.
4. Cliquer sur **Launch** pour démarrer le job.
5. **Suivre l'exécution** : AWX bascule automatiquement sur l'écran de job
   en cours, avec les tâches qui s'exécutent une à une (visible en temps
   réel) :
   1. Installer le paquet web (`nginx`)
   2. Créer l'utilisateur système applicatif (`appsvc`)
   3. S'assurer que le répertoire de config existe (`/etc/myapp`)
   4. Déployer la config applicative (`app.conf`, redémarre le service si
      le contenu a changé)
   5. Activer et démarrer le service web
6. **Lire les logs** : chaque tâche affiche son statut en couleur —
   - vert (`ok`) : état déjà conforme, rien à faire (idempotence) ;
   - jaune (`changed`) : la tâche a modifié l'état du système ;
   - rouge (`failed`) : la tâche a échoué — voir §6 Dépannage.
   Cliquer sur une tâche déroule le détail (module utilisé, sortie
   complète) — utile pour comprendre exactement ce qui s'est passé.
7. Le job se termine avec le statut global **Successful** (vert) ou
   **Failed** (rouge) en haut de l'écran. Le résultat complet reste
   consultable dans l'historique (**Jobs** dans le menu de gauche).

---

## 5. Planifications (Schedules)

Le Job Template `webserver-provision` dispose d'une planification nommée
**`nightly-drift-check`**, qui le relance automatiquement chaque nuit
(quotidien, 02:00 UTC) pour vérifier/corriger une éventuelle dérive de
configuration (« drift ») — c'est l'équivalent du trigger cron qu'aurait pu
avoir un job Jenkins.

**Pour consulter ou vérifier une planification :**

1. Depuis la fiche du Job Template `webserver-provision`, ouvrir l'onglet
   **Schedules**.
2. Repérer l'entrée **`nightly-drift-check`** : elle indique la fréquence
   (quotidienne) et la prochaine date d'exécution.
3. Les jobs lancés automatiquement par cette planification apparaissent
   dans **Jobs** au même titre qu'un lancement manuel, avec la mention
   « Launched by: Schedule ».

> Les planifications sont définies en configuration versionnée
> (`awx/schedules.yml`) — voir Partie C, §10, pour les modifier via le code
> plutôt que dans l'UI (l'UI serait écrasée au prochain `apply.yml`).

---

## 6. Dépannage

### Erreurs SSH (connexion à l'hôte cible impossible)

**Symptôme :** le job échoue tôt, avec un message du type
`UNREACHABLE! => ... Failed to connect ...` ou `Permission denied
(publickey)`.

**Actions :**
1. Vérifier que le credential **`dev-machine`** est bien celui sélectionné
   sur le Job Template (fiche détail, section Credentials).
2. Demander à un développeur/administrateur de vérifier que la clé SSH
   associée au credential est à jour (voir Partie D, §11 « Secrets »).
3. Vérifier que l'hôte cible (`web1` dans l'inventaire `dev`) est bien
   joignable réseau depuis l'Execution Environment AWX.
4. Relancer le job une fois le problème corrigé (bouton **Relaunch** sur la
   page de détail du job).

### Échec de synchronisation SCM (Project)

**Symptôme :** le job échoue avant même de démarrer les tâches, avec une
erreur liée au **Project** (ex. `Failed to update project`), ou le contenu
exécuté semble être une ancienne version du playbook.

**Actions :**
1. Aller dans **Projects** (menu de gauche), ouvrir **`ansible-solution`**.
2. Vérifier le statut du dernier **SCM sync** (icône de synchronisation) —
   un échec y est détaillé (URL GitLab inaccessible, branche introuvable,
   credential SCM invalide).
3. Cliquer sur l'icône de synchronisation pour relancer un sync manuel.
4. Si l'erreur persiste, vérifier avec un développeur que le dépôt GitLab
   est accessible et que la branche `main` existe (le Project est
   configuré avec `scm_update_on_launch: true`, donc un sync est tenté
   automatiquement à chaque lancement).

### Échec du health check (vérification de service)

**Symptôme :** dans les tâches du job, l'étape liée à la vérification de
port/service échoue, ou l'application ne répond pas après le job.

**Actions :**
1. Vérifier dans les logs du job que l'étape « Activer et démarrer le
   service web » est bien passée en `ok`/`changed` (pas `failed`) avant le
   health check.
2. Sur l'hôte cible, vérifier manuellement que le service (`nginx`) est
   actif : `systemctl status nginx`.
3. Vérifier que le port déclaré dans le Survey (`app_port`, défaut `8080`)
   correspond bien à celui utilisé par la configuration déployée
   (`/etc/myapp/app.conf`, champ `listen_port`).
4. Le health check est un cas particulier « encapsulé » (script glue, non
   converti en tâches Ansible déclaratives) — voir le
   [catalogue de conversion](../conversion-catalog.md) pour le détail de
   son traitement et son évolution prévue en tranche ultérieure.
5. Si le problème persiste, transmettre le lien du job (échec) à un
   développeur pour investigation (voir Partie C et D pour la structure du
   projet et les Execution Environments).

**Suite du guide :**
- Partie A — [Vue d'ensemble & concepts](01-vue-ensemble.md)
- Partie C — [Guide développeur](03-guide-developpeur.md)
- Partie D — [Référence & exploitation](04-reference-exploitation.md)
