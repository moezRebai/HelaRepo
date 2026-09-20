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
