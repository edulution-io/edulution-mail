# Debug Mode - Aktivierung

## Debug-Logging aktivieren

Um detaillierte Debug-Informationen zu erhalten, setze die Umgebungsvariable `LOG_LEVEL=DEBUG`.

### In docker-compose.yml

```yaml
services:
  edulution-mail:
    environment:
      - LOG_LEVEL=DEBUG
```

### Direkt beim Container-Start

```bash
docker run -e LOG_LEVEL=DEBUG ...
```

### Für einen laufenden Container neu starten

```bash
# In docker-compose.yml LOG_LEVEL=DEBUG hinzufügen, dann:
docker-compose up -d edulution-mail
```

## Was wird geloggt?

Im Debug-Mode werden zusätzlich geloggt:

1. **Typ-Informationen bei Alias-Deletion**
   - ID und Address Typen
   - Finale alias_id Typ

2. **Deletion Candidates Detail-Informationen**
   - Jedes Item mit seinem Datentyp
   - Hilft beim Debuggen von Type-Errors

## Beispiel Debug-Output

```
DEBUG: 2025-11-05 16:30:00,123   * [DEBUG] Processing alias for deletion: id=148 (type: int), address=None (type: NoneType), final alias_id=148 (type: int)
DEBUG: 2025-11-05 16:30:00,124   * [DEBUG] aliases items and types:
DEBUG: 2025-11-05 16:30:00,124     - 148 (type: int)
```

## Standard-Logging (ohne Debug)

Standard ist `LOG_LEVEL=INFO`:
- Zeigt normale Sync-Informationen
- Zeigt Warnungen und Fehler
- Keine Debug-Details

## Debug-Mode wieder deaktivieren

Entferne `LOG_LEVEL=DEBUG` aus der Konfiguration oder setze es auf `INFO`:

```yaml
services:
  edulution-mail:
    environment:
      - LOG_LEVEL=INFO  # oder ganz weglassen
```

Dann Container neu starten:
```bash
docker-compose up -d edulution-mail
```
