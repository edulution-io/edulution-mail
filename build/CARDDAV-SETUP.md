# CardDAV Global Address Books Setup

## Übersicht

Dieses Feature stellt die globalen Adressbücher (GAL) von Mailcow über CardDAV/WebDAV zur Verfügung. Damit können externe Clients wie Thunderbird, Apple Contacts, Android, etc. die globalen Kontakte einbinden.

## Verfügbare Adressbücher

Nach der Einrichtung stehen zwei CardDAV-Adressbücher zur Verfügung:

1. **Benutzer** (`/carddav/users/`)
   - Alle Mailboxen (Hauptadressen)
   - Alle sichtbaren Aliase
   - Read-only Zugriff

2. **Gruppen** (`/carddav/groups/`)
   - Alle Verteilerlisten / Mailgruppen
   - Mit aufgelösten Mitgliedern
   - Read-only Zugriff

## Automatische Installation

Die CardDAV-Server-Komponente wird automatisch mit dem Container gestartet:

1. **CardDAV-Server**: Läuft auf Port 8800 (intern)
2. **Datensynchronisation**: Aktualisiert sich automatisch alle 60 Sekunden aus der `edulution_gal` MySQL-View
3. **Protokollierung**: Logs verfügbar unter `/app/carddav-server.log`

## Nginx-Konfiguration einrichten

Um die CardDAV-Adressbücher von außen erreichbar zu machen, muss die Nginx-Konfiguration in Mailcow angepasst werden:

### Option 1: Manuelle Konfiguration

1. Kopieren Sie den Inhalt von `carddav-nginx.conf` in die Mailcow Nginx-Konfiguration:

```bash
# Öffnen oder erstellen Sie die site.conf
nano /opt/mailcow-dockerized/data/conf/nginx/site.conf
```

2. Fügen Sie folgende Zeilen hinzu:

```nginx
# CardDAV Global Address Books
location /carddav/ {
    proxy_pass http://edulution:8800/carddav/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Depth $http_depth;

    proxy_buffering off;
    proxy_request_buffering off;
    proxy_http_version 1.1;

    add_header Access-Control-Allow-Origin * always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PROPFIND, REPORT" always;
    add_header Access-Control-Allow-Headers "Content-Type, Depth, Prefer, Authorization" always;
}
```

3. Nginx neu laden:

```bash
docker exec nginx-mailcow nginx -s reload
```

### Option 2: Automatische Integration (empfohlen)

Die Nginx-Konfiguration kann auch automatisch in `entrypoint.sh` eingefügt werden. Dies wird in einer zukünftigen Version implementiert.

## Client-Einrichtung

### Thunderbird (CardBook Add-on)

1. Installieren Sie das Add-on "CardBook"
2. CardBook öffnen → Neues Adressbuch → Remote → CardDAV
3. URL eingeben:
   - **Benutzer**: `https://mail.example.com/carddav/users/`
   - **Gruppen**: `https://mail.example.com/carddav/groups/`
4. Optional: Authentifizierung konfigurieren (wenn aktiviert)
5. Synchronisationsintervall einstellen

### Apple Kontakte (macOS/iOS)

1. Systemeinstellungen → Accounts → Account hinzufügen → CardDAV
2. **Server**: `mail.example.com`
3. **Benutzername**: (leer lassen, wenn keine Auth)
4. **Pfad**: `/carddav/users/` oder `/carddav/groups/`

### Android (DAVx⁵)

1. DAVx⁵ aus F-Droid oder Play Store installieren
2. Konto hinzufügen → Mit URL und Benutzername anmelden
3. **Basis-URL**: `https://mail.example.com/carddav/`
4. Adressbücher auswählen (users und/oder groups)

### Evolution (Linux)

1. Datei → Neu → Adressbuch
2. Typ: CardDAV
3. **URL**: `https://mail.example.com/carddav/users/`

## Technische Details

### Architektur

```
MySQL (edulution_gal View)
    ↓
CardDAV-Server (Python, Port 8800)
    ↓ (Proxy)
Nginx (https://mail.example.com/carddav/)
    ↓
CardDAV Clients
```

### vCard-Format

Der Server generiert vCards im Format **vCard 3.0** mit folgenden Feldern:

**Für Benutzer:**
- `UID`: Eindeutige ID aus `c_uid`
- `FN`: Vollständiger Name aus `c_cn`
- `N`: Nachname/Vorname aus `c_sn` / `c_givenname`
- `EMAIL`: E-Mail-Adresse

**Für Gruppen:**
- `UID`: Gruppen-ID
- `FN`: Gruppenname
- `KIND`: group
- `EMAIL`: Gruppen-E-Mail
- `X-ADDRESSBOOKSERVER-MEMBER`: Liste der Mitglieder (als mailto: URIs)

### Performance

- **Cache**: Kontakte werden alle 60 Sekunden aus der Datenbank geladen
- **Memory**: Ca. 1.5 KB pro Benutzer, 2 KB pro Gruppe
- **Refresh**: Automatisch im Hintergrund-Thread
- **Skalierung**: Getestet mit bis zu 2000 Kontakten

## Fehlersuche

### Server läuft nicht

```bash
# Log-Datei prüfen
docker exec edulution-mail cat /app/carddav-server.log

# Server-Status prüfen
docker exec edulution-mail ps aux | grep carddav
```

### Clients können nicht verbinden

1. **Nginx-Konfiguration prüfen:**
   ```bash
   docker exec nginx-mailcow nginx -t
   ```

2. **Netzwerk-Verbindung testen:**
   ```bash
   curl -v https://mail.example.com/carddav/
   ```

3. **Port-Weiterleitung prüfen:**
   ```bash
   docker exec edulution-mail netstat -tuln | grep 8800
   ```

### Debug-Modus aktivieren

```bash
# In docker-compose.yml oder .env
CARDDAV_DEBUG=true
```

Dann Container neu starten und `/app/carddav-server.log` prüfen.

## Sicherheit

### Authentifizierung

Aktuell läuft der CardDAV-Server **ohne Authentifizierung** (read-only Zugriff auf öffentliche GAL-Daten).

Um Authentifizierung zu aktivieren:

1. Nginx-Konfiguration erweitern:
   ```nginx
   location /carddav/ {
       auth_request /auth.php;
       # ... rest der Config
   }
   ```

2. Oder: OAuth2-Proxy vorschalten

### Firewall

Stellen Sie sicher, dass Port 8800 **nur intern** im Docker-Netzwerk erreichbar ist. Externer Zugriff sollte **nur über Nginx** (HTTPS) erfolgen.

## Weitere Informationen

- **LDAP-Server**: Läuft parallel auf Port 3890 (für SOGo)
- **MySQL-View**: `edulution_gal` enthält die Quelldaten
- **Protokoll**: CardDAV (RFC 6352), WebDAV (RFC 4918)

## Limitierungen

- **Read-only**: Kontakte können nicht über CardDAV bearbeitet werden
- **Kein Caching auf Client-Seite**: Clients müssen ETags verwenden
- **Keine Authentifizierung**: Derzeit offener Zugriff (kann erweitert werden)

## Roadmap

- [ ] Authentifizierung über Mailcow-API
- [ ] Automatische Nginx-Konfiguration
- [ ] Support für vCard 4.0
- [ ] Caching-Optimierungen
- [ ] WebDAV-Sync-Collection Support
