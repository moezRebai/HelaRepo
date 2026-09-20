#!/usr/bin/env bash
# Exécute le script legacy dans un conteneur et capture l'état final.
set -euo pipefail
CID=$(docker run -d --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  geerlingguy/docker-ubuntu2204-ansible:latest /lib/systemd/systemd)
# Cleanup sur TOUT chemin de sortie (succès ou échec) pour ne pas fuiter le conteneur.
trap 'docker rm -f "$CID" >/dev/null 2>&1 || true' EXIT
docker cp fake-source/infra-provisioning "$CID":/src
docker exec "$CID" bash -c "cd /src && APP_PORT=8080 bash provision.sh" || true
docker exec "$CID" bash -c "dpkg -s nginx | grep Status; getent passwd appsvc; cat /etc/myapp/app.conf" > /tmp/source_state.txt
echo "État source -> /tmp/source_state.txt"; cat /tmp/source_state.txt
