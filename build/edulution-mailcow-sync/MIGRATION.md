# Migration zu Marker-basiertem Management

## Problem

Nach dem Update auf das neue Marker-System werden bestehende Mailboxen und Aliases nicht automatisch mit Markern versehen, weil sie als "keine Änderung" erkannt werden.

## Lösung: Force Marker Update Mode

Setze einmalig die Environment Variable `FORCE_MARKER_UPDATE=1` um alle bestehenden managed Objekte mit Markern zu versehen.

### Schritt 1: Force Update aktivieren

In `docker-compose.yml` oder Environment:

```yaml
services:
  edulution-mail:
    environment:
      - FORCE_MARKER_UPDATE=1
```

### Schritt 2: Container neu starten

```bash
docker-compose up -d edulution-mail
```

### Schritt 3: Logs prüfen

```bash
docker logs -f edulution-mail
```

Du siehst:
```
WARNING: ========================================================
WARNING: * FORCE_MARKER_UPDATE MODE ENABLED
WARNING: * All managed objects will be updated with markers
WARNING: * Remove FORCE_MARKER_UPDATE=1 after this sync!
WARNING: ========================================================

INFO: * Going to update XXX mailbox(es)
INFO: * Going to update XXX alias(es)
```

### Schritt 4: Force Update deaktivieren

Nach erfolgreichem Sync **entferne** `FORCE_MARKER_UPDATE=1`:

```yaml
services:
  edulution-mail:
    environment:
      # - FORCE_MARKER_UPDATE=1  # <-- Auskommentieren oder löschen
```

Dann Container neu starten:
```bash
docker-compose up -d edulution-mail
```

## Was passiert?

Mit `FORCE_MARKER_UPDATE=1`:
- **Mailboxen**: Tag `edulution-sync-managed` wird hinzugefügt (auch wenn `tags` Array schon existiert)
- **Aliases**: `private_comment` wird auf `#### managed-by-edulution-sync ####` gesetzt (überschreibt alte Werte)

## Nach der Migration

Nach der Migration sind alle vom Sync verwalteten Objekte mit Markern versehen:
- Nur Objekte **MIT** Markern werden vom Sync verwaltet
- Objekte **OHNE** Marker bleiben unangetastet (manuelle Objekte)
- `DELETE_ENABLED=0` verhindert versehentliches Löschen

## Troubleshooting

### "No changes for mailbox(es)/aliases"

Wenn du das siehst **OBWOHL** `FORCE_MARKER_UPDATE=1` gesetzt ist:
- Prüfe ob die Variable wirklich im Container ankommt: `docker exec edulution-mail env | grep FORCE`
- Stelle sicher dass der Container nach dem Setzen neu gestartet wurde

### Aliases haben falsche Comments

Wenn Aliases vorher custom `private_comment` Werte hatten:
- Diese werden überschrieben mit dem Management-Marker
- Das ist gewollt für einheitliches Management
- Wenn du die alten Comments behalten willst, musst du sie manuell wiederherstellen

## Automatische Migration (ohne FORCE_MARKER_UPDATE)

**Aliases** sollten automatisch migriert werden, weil die `_checkElementValueDelta` Methode immer True zurückgibt wenn der Marker fehlt.

**Mailboxen** sollten auch automatisch migriert werden, weil `tags` ein neuer Key ist.

Aber wenn es nicht funktioniert, nutze `FORCE_MARKER_UPDATE=1` um sicher zu gehen.
