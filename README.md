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
| SYNC_INTERVAL                  | No                | 60                                                 | (seconds) The sync interval for user and groups |
| KEYCLOAK_SERVER_URL            | No                | https://edulution-traefik/auth/                    | The default keycloak server (edulution) |
| MAILCOW_TZ                     | No                | Europe/Berlin                                      | Mailcow timezone |
| MAILCOW_BRANCH                 | No                | master                                             | Mailcow branche (master / nightly) |
||
| KEYCLOAK_CLIENT_ID             | Yes               |                                                    | Client-ID for login in keycloak |
| KEYCLOAK_SECRET_KEY            | Yes               |                                                    | Secret-Key for login in keycloak |
||
| MAILCOW_HOSTNAME               | Yes               |                                                    | Hostname of the mailserver (eg. mail.demo.multi.schule) |
| MAILCOW_PATH                   | Yes               |                                                    | Mailcow path: Should always set to "${PWD}" |
