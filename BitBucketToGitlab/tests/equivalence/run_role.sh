#!/usr/bin/env bash
# Exécute le role via le playbook site.yml (Task 4) et capture l'état final.
#
# IMPORTANT : site.yml cible `hosts: webservers`. L'inventaire doit donc placer
# le conteneur dans le groupe `webservers` (et non sous `all.hosts`), sinon la
# play ne matche aucun hôte et le test "réussit" de façon fallacieuse
# (0 host matched != équivalence prouvée).
set -euo pipefail
docker rm -f eq-role >/dev/null 2>&1 || true
CID=$(docker run -d --name eq-role --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  geerlingguy/docker-ubuntu2204-ansible:latest /lib/systemd/systemd)
# Cleanup sur TOUT chemin de sortie (succès ou échec) pour ne pas fuiter le conteneur.
trap 'docker rm -f eq-role >/dev/null 2>&1 || true' EXIT
cat > /tmp/eq_inv.yml <<EOF
all:
  children:
    webservers:
      hosts:
        eq-role:
          ansible_connection: docker
EOF
ansible-playbook -i /tmp/eq_inv.yml ansible-solution/playbooks/site.yml
docker exec "$CID" bash -c "dpkg -s nginx | grep Status; getent passwd appsvc; cat /etc/myapp/app.conf" > /tmp/role_state.txt
echo "État role -> /tmp/role_state.txt"; cat /tmp/role_state.txt
