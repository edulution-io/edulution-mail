#!/bin/bash

# Add LDAP group source for SOGo
# This enables native group expansion in calendar invitations and mail composer

domain="$1"
gal_status="$2"

# Point to our internal SQL-to-LDAP bridge
LDAP_HOST="127.0.0.1:3893"
LDAP_BIND_DN="cn=admin,dc=edulution,dc=local"
LDAP_BIND_PASS="any"

echo "                <dict>
                    <key>type</key>
                    <string>ldap</string>
                    <key>id</key>
                    <string>${domain}_ldap_groups</string>
                    <key>displayName</key>
                    <string>Linuxmuster Gruppen (${domain})</string>
                    <key>canAuthenticate</key>
                    <string>NO</string>
                    <key>isAddressBook</key>
                    <string>YES</string>

                    <key>hostname</key>
                    <string>ldap://${LDAP_HOST}:389</string>
                    <key>bindDN</key>
                    <string>${LDAP_BIND_DN}</string>
                    <key>bindPassword</key>
                    <string>${LDAP_BIND_PASS}</string>

                    <key>baseDN</key>
                    <string>ou=groups,dc=edulution,dc=local</string>
                    <key>filter</key>
                    <string>(objectClass=groupOfNames)</string>

                    <key>IDFieldName</key>
                    <string>cn</string>
                    <key>CNFieldName</key>
                    <string>cn</string>
                    <key>UIDFieldName</key>
                    <string>sAMAccountName</string>
                    <key>MailFieldNames</key>
                    <array>
                        <string>mail</string>
                    </array>

                    <key>GroupObjectClasses</key>
                    <array>
                        <string>groupOfNames</string>
                    </array>

                    <key>listRequiresDot</key>
                    <string>NO</string>
                </dict>"
