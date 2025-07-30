# EDULUTION-MAIL

Integration of Mailcow in edulution and linuxmuster. User mailboxes, aliases and distribution groups are read from Keycloak or Linuxmuster and automatically synchronized. The login in IMAP is done via Keycloak and the login in the SOGO webmailer works via Keycloak authorization token.

## Installation

via EdulutionUI

## How does it work

### Synchronization

Synchronization takes place at definable intervals. The interval can be set using the environment variable "SYNC_INTERVAL". All new domains, users and groups are created, edited, deactivated or deleted.

### Login

The login with IMAP, POP3 and SMTP takes place in the dovecot container via a LUA script. The script "edulution-sso.lua" is now integrated here, which forwards every login attempt to the Edulution Mail API, which in turn attempts a login via Keycloak or LDAP.

A direct login in SOGO is currently not possible. The login is carried out via the URL "http://<MAILSERVER>/sogo-auth.php" with the GET parameter "token" or the authorization header. The token is then checked via the Edulution Mail API with Keycloak and if successful, you are redirected to the SOGO webmail.

## Environment variables

| Environment variables          | Required?         | Default                                            | Description                               |
|--------------------------------|-------------------|----------------------------------------------------|-------------------------------------------|
| DEFAULT_USER_QUOTA             | No                | 1000                                               | (MB) The default mailbox quota for a user |
| DOMAIN_QUOTA                   | No                | 10240                                              | (MB) The quota for the whole domain. The user quota is reserved. If the total user quota is larger than the domain quota, the sync will be stopped! |
| GROUPS_TO_SYNC                 | No                | role-schooladministrator,role-teacher,role-student | A comma seperated list of groups of which the users will be synced
| ENABLE_GAL                     | No                | 1 (YES)                                            | Enable (1) or disable (0) the GAL (Global Address List) |
| SYNC_INTERVAL                  | No                | 300                                                | (seconds) The sync interval for user and groups |
| KEYCLOAK_SERVER_URL            | No                | https://edulution-traefik/auth/                    | The default keycloak server (edulution) |
| MAILCOW_TZ                     | No                | Europe/Berlin                                      | Mailcow timezone |
| MAILCOW_API_TOKEN              | No                | <will be generated>                                | Define an api token to use. Schould be somthing like aaaaa-bbbbb-ccccc-ddddd-eeeee |
| MAILCOW_BRANCH                 | No                | master                                             | Mailcow branche (master / nightly) |
| KEYCLOAK_CLIENT_ID             | No               | edu-mailcow-sync                                    | Client-ID for login in keycloak |
||
| KEYCLOAK_SECRET_KEY            | Yes               |                                                    | Secret-Key for login in keycloak |
||
| MAILCOW_HOSTNAME               | Yes               |                                                    | Hostname of the mailserver (eg. mail.demo.multi.schule) |
| MAILCOW_PATH                   | Yes               |                                                    | Mailcow path: Should always set to "/srv/docker/edulution-mail" |

## Manual deployment

Use **docker-compose.yml** or this docker run command:

```
docker run -d \
  --name edulution-mail \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /srv/docker/edulution-mail:/srv/docker/edulution-mail \
  -e MAILCOW_HOSTNAME=mail.dev.multi.schule \
  -e MAILCOW_PATH=/srv/docker/edulution-mail \
  -e KEYCLOAK_SECRET_KEY=UIZvGG0JVDZaUEvLElwBfuqA64gMWTIl \
  ghcr.io/edulution-io/edulution-mail
```

## Override environment variables

You can override the environment variables in the **mail.override.config** file in the MAILCOW_PATH directory. The file must be in JSON format and can look like this:

```
{
  "DEFAULT_USER_QUOTA": 1000,
  "GROUPS_TO_SYNC": "role-schooladministrator,role-teacher,role-student",
  "DOMAIN_QUOTA": 10240,
  "ENABLE_GAL": 1,
  "SYNC_INTERVAL": 300
}
```

## Temporarily disable sync

If you want to temporarily disable the sync (eg. for backup or restore) you can create a file called **DISABLE_SYNC** in the MAILCOW_PATH directory.

```bash
touch /srv/docker/edulution-mail/DISABLE_SYNC
```

The sync will check if the file exists on every run (see SYNC_INTERVAL) and skip the sync if the file exists.