#!/bin/bash

# Add LDAP group source for SOGo
# This enables native group expansion in calendar invitations and mail composer

domain="$1"
gal_status="$2"

# LDAP credentials from linuxmuster
LDAP_HOST="10.0.0.1"
LDAP_BIND_DN="CN=edulutionui-binduser,OU=Management,OU=GLOBAL,DC=linuxmuster,DC=lan"
LDAP_BIND_PASS="MAvNhbqBHyDcPY)3qygC8"

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
                    <string>OU=Groups,OU=Global,DC=linuxmuster,DC=lan</string>
                    <key>filter</key>
                    <string>(objectClass=group)</string>

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
                        <string>group</string>
                    </array>

                    <key>listRequiresDot</key>
                    <string>NO</string>
                </dict>"
