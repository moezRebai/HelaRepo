# Test d'équivalence source ↔ cible

## Objectif

Prouver que le role Ansible `webserver` (cible, `ansible-solution/roles/webserver`,
assemblé par `ansible-solution/playbooks/site.yml`) produit **le même état final**
que le script legacy `fake-source/infra-provisioning/provision.sh` (source), afin
de valider que la conversion Bitbucket → GitLab/Ansible est comportementalement
neutre.

L'état final comparé porte sur les trois effets observables du script legacy :

- le paquet `nginx` est installé (`dpkg -s nginx`, ligne `Status`) ;
- l'utilisateur système `appsvc` existe (`getent passwd appsvc`) ;
- la configuration applicative `/etc/myapp/app.conf` a le contenu attendu
  (`listen_port=8080`, `run_as=appsvc`).

## Prérequis

- La collection `community.docker` doit être installée sur la machine qui
  exécute les tests (`ansible-galaxy collection install community.docker`),
  car l'inventaire du test d'équivalence utilise `ansible_connection: docker`
  pour piloter les conteneurs.

## Comment ça marche

- `run_source.sh` : démarre un conteneur `geerlingguy/docker-ubuntu2204-ansible`
  (systemd actif), y copie `fake-source/infra-provisioning`, exécute
  `provision.sh` avec `APP_PORT=8080`, puis capture l'état ci-dessus dans
  `/tmp/source_state.txt`.
- `run_role.sh` : démarre un second conteneur (`eq-role`) et exécute
  `ansible-solution/playbooks/site.yml` dessus via la connexion Ansible
  `docker`, puis capture le même état dans `/tmp/role_state.txt`.

  **Point d'attention** : `site.yml` cible `hosts: webservers`. L'inventaire
  généré place donc bien le conteneur dans le groupe `webservers` :

  ```yaml
  all:
    children:
      webservers:
        hosts:
          eq-role:
            ansible_connection: docker
  ```

  Un inventaire qui placerait le conteneur sous `all.hosts` (en dehors du
  groupe `webservers`) ferait matcher zéro hôte : la play ne s'exécuterait
  jamais et le test « réussirait » de façon totalement fallacieuse (aucun
  changement, donc aucune différence détectée). Vérifier systématiquement,
  dans la sortie `ansible-playbook`, un récap avec `ok=… changed=…` sur
  `eq-role` (et pas `skipping: no hosts matched`).

- `compare.sh` : orchestre les deux scripts puis fait un `diff -u` des deux
  captures d'état. Sortie attendue :

  ```
  ÉQUIVALENT : état final identique.
  ```

## Lancer le test

Depuis la racine du dépôt, avec Docker et `ansible-playbook` disponibles :

```bash
bash tests/equivalence/compare.sh
```

## Ce que le test ne couvre pas (et pourquoi ce n'est pas un problème)

- Il ne compare pas l'exécution du `health_check.py` du script legacy (celui-ci
  dépend d'un port HTTP réellement joignable) : `run_source.sh` tolère son
  échec (`|| true`) pour ne pas polluer l'état capturé, qui porte uniquement
  sur les effets de provisioning (paquet, utilisateur, config).
- Il ne compare qu'un seul run de chaque côté. La valeur ajoutée du role par
  rapport au script legacy est l'**idempotence** : `provision.sh` n'est pas
  garanti idempotent tel quel (il relance `systemctl restart nginx` à chaque
  exécution, entre autres), alors que le role webserver, lui, a été validé
  idempotent par les tests Molecule de la Task 3 (deuxième `ansible-playbook`
  run → `changed=0`). Ce test d'équivalence porte donc sur l'état final après
  un seul run côté source et côté cible ; l'idempotence de la cible est une
  propriété supplémentaire, pas régressive, apportée par la conversion.
