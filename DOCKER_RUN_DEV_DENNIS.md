# Docker Run Anleitung für dev-dennis Tag

## Container stoppen und löschen

```bash
# Container stoppen
docker stop edulution-mail

# Container löschen
docker rm edulution-mail
```

## Neues Image pullen

```bash
# Neues dev-dennis Image herunterladen
docker pull ghcr.io/edulution-io/edulution-mail:dev-dennis
```

## Container mit dev-dennis Tag starten

```bash
docker run -d \
  --name edulution-mail \
  --network mailcowdockerized_mailcow-network \
  --restart unless-stopped \
  -e MAILCOW_PATH=/opt/mailcow-dockerized \
  -e KEYCLOAK_URL=https://keycloak.edulution.io \
  -e KEYCLOAK_REALM=Edulution \
  -e KEYCLOAK_CLIENT_ID=mailcow \
  -e KEYCLOAK_CLIENT_SECRET=<dein-secret> \
  -e MAILCOW_API_KEY=<dein-api-key> \
  -e MAILCOW_HOSTNAME=mail.edulution.io \
  -v /opt/mailcow-dockerized:/opt/mailcow-dockerized \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ghcr.io/edulution-io/edulution-mail:dev-dennis
```

## Logs verfolgen

```bash
# Alle Logs
docker logs -f edulution-mail

# Nur Patch-bezogene Logs
docker logs -f edulution-mail | grep -i patch

# Nur Gruppen-bezogene Logs
docker logs -f edulution-mail | grep -i group
```

## Patch-Status prüfen

```bash
# Host-Marker prüfen
ls -la /opt/mailcow-dockerized/data/.sogo-patches-applied

# Container-Marker prüfen
docker exec mailcowdockerized-sogo-mailcow-1 \
  test -f /usr/lib/GNUstep/SOGo/.sogo-patches-applied && \
  echo "✅ Patches applied" || \
  echo "❌ Patches NOT applied"
```

## Erwartete Log-Ausgabe bei erfolgreichem Patch

```
[INFO] Applying SOGo patches for SQL group support
[INFO] Waiting for SOGo container... (1/60)
[SUCCESS] SOGo container is running
[INFO] Installing patch utility in SOGo container
[INFO] Copying patches to SOGo container
[INFO] Applying calendar groups patch
patching file 'SoObjects/Appointments/SOGoAppointmentFolder.m'
[SUCCESS] Calendar patch applied
[INFO] Applying contacts groups patch
patching file 'UI/Contacts/UIxContactView.m'
[SUCCESS] Contacts patch applied
[SUCCESS] SOGo patches applied successfully
[INFO] Restarting SOGo container to apply patches
[SUCCESS] SOGo restarted with patches applied
```

## Troubleshooting

### Patches werden nicht angewendet

```bash
# Marker-Dateien löschen
sudo rm -f /opt/mailcow-dockerized/data/.sogo-patches-applied
docker exec mailcowdockerized-sogo-mailcow-1 \
  rm -f /usr/lib/GNUstep/SOGo/.sogo-patches-applied

# Container neu starten
docker restart edulution-mail
```

### "Image not found" Fehler

```bash
# Prüfen ob GitHub Actions den Build abgeschlossen hat
# https://github.com/edulution-io/edulution-mail/actions

# Warten bis der Workflow "Build docker image" für dev-dennis fertig ist
# Dann erneut pullen:
docker pull ghcr.io/edulution-io/edulution-mail:dev-dennis
```

## Zurück zu latest Tag

```bash
# Container stoppen und löschen
docker stop edulution-mail
docker rm edulution-mail

# Latest Tag starten (wie oben, aber mit :latest statt :dev-dennis)
docker run -d \
  --name edulution-mail \
  --network mailcowdockerized_mailcow-network \
  --restart unless-stopped \
  -e MAILCOW_PATH=/opt/mailcow-dockerized \
  -e KEYCLOAK_URL=https://keycloak.edulution.io \
  -e KEYCLOAK_REALM=Edulution \
  -e KEYCLOAK_CLIENT_ID=mailcow \
  -e KEYCLOAK_CLIENT_SECRET=<dein-secret> \
  -e MAILCOW_API_KEY=<dein-api-key> \
  -e MAILCOW_HOSTNAME=mail.edulution.io \
  -v /opt/mailcow-dockerized:/opt/mailcow-dockerized \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ghcr.io/edulution-io/edulution-mail:latest
```

## Nächste Schritte nach erfolgreichem Patch

1. Warte bis Container läuft und Patches angewendet wurden
2. Öffne `TESTING_INSTRUCTIONS.md`
3. Folge den Test-Anweisungen für:
   - SQL-Abfragen zum Prüfen der Gruppen
   - Kalendereinladungen an Gruppen
   - E-Mail Composer Gruppen-Expansion
