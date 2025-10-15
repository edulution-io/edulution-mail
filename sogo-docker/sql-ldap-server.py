#!/usr/bin/env python3
"""
SQL-to-LDAP Gateway for SOGo
Emulates an LDAP server that reads data from MySQL edulution_gal
"""

import socket
import struct
import sys
import os
import mysql.connector
from pyasn1.codec.ber import encoder, decoder
from pyasn1.type import univ, namedtype, tag

# LDAP ASN.1 structures
class LDAPMessage(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('messageID', univ.Integer()),
        namedtype.NamedType('protocolOp', univ.Choice(componentType=namedtype.NamedTypes(
            namedtype.NamedType('bindRequest', univ.Sequence()),
            namedtype.NamedType('searchRequest', univ.Sequence()),
        )))
    )

class LDAPBindResponse(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('resultCode', univ.Integer()),
        namedtype.NamedType('matchedDN', univ.OctetString()),
        namedtype.NamedType('diagnosticMessage', univ.OctetString())
    )

class LDAPSearchResultEntry(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('objectName', univ.OctetString()),
        namedtype.NamedType('attributes', univ.SequenceOf(componentType=univ.Sequence()))
    )

# Database connection
def get_db():
    return mysql.connector.connect(
        unix_socket='/var/run/mysqld/mysqld.sock',
        user=os.getenv('DBUSER', 'mailcow'),
        password=os.getenv('DBPASS', ''),
        database=os.getenv('DBNAME', 'mailcow')
    )

def query_group(group_cn):
    """Query group and its members from edulution_gal"""
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get group info
    cursor.execute("""
        SELECT c_uid, c_cn, mail, groupMembers, isGroup
        FROM edulution_gal
        WHERE c_uid = %s AND isGroup = 1
    """, (group_cn,))

    group = cursor.fetchone()
    if not group:
        return None

    # Get members
    member_emails = group['groupMembers'].split() if group['groupMembers'] else []
    members = []

    for email in member_emails:
        cursor.execute("""
            SELECT c_uid, c_cn, mail, c_givenname, c_sn
            FROM edulution_gal
            WHERE c_uid = %s OR mail = %s
            LIMIT 1
        """, (email, email))

        member = cursor.fetchone()
        if member:
            members.append(member)

    cursor.close()
    db.close()

    return {'group': group, 'members': members}

def handle_bind_request(message_id):
    """Handle LDAP bind request - always success"""
    response = LDAPMessage()
    response['messageID'] = message_id

    bind_resp = LDAPBindResponse()
    bind_resp['resultCode'] = 0  # success
    bind_resp['matchedDN'] = ''
    bind_resp['diagnosticMessage'] = ''

    response['protocolOp'] = ('bindResponse', bind_resp)
    return encoder.encode(response)

def handle_search_request(message_id, base_dn, filter_str):
    """Handle LDAP search request"""
    print(f"[LDAP] Search: baseDN={base_dn}, filter={filter_str}")

    # Parse filter to extract group CN
    # Simple parsing for (cn=GROUP_NAME)
    if 'cn=' in filter_str:
        group_cn = filter_str.split('cn=')[1].split(')')[0]
        data = query_group(group_cn)

        if data:
            # Return search entry with group members as 'member' attribute
            entries = []

            for member in data['members']:
                member_dn = f"cn={member['c_uid']},ou=users,dc=edulution,dc=local"

                entry = LDAPSearchResultEntry()
                entry['objectName'] = member_dn
                # Add attributes...

                msg = LDAPMessage()
                msg['messageID'] = message_id
                msg['protocolOp'] = ('searchResEntry', entry)
                entries.append(encoder.encode(msg))

            return b''.join(entries)

    # Empty search result
    return b''

def handle_client(client_socket):
    """Handle LDAP client connection"""
    try:
        data = client_socket.recv(4096)
        if not data:
            return

        # Decode LDAP message
        message, remainder = decoder.decode(data, asn1Spec=LDAPMessage())
        message_id = int(message['messageID'])

        # Handle different operations
        if 'bindRequest' in message['protocolOp']:
            response = handle_bind_request(message_id)
            client_socket.send(response)

        elif 'searchRequest' in message['protocolOp']:
            # Extract search parameters
            search_req = message['protocolOp']['searchRequest']
            # ... parse and handle search

            response = handle_search_request(message_id, '', '')
            client_socket.send(response)

    except Exception as e:
        print(f"[LDAP] Error: {e}")

    finally:
        client_socket.close()

def main():
    """Start LDAP server on port 3893"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 3893))
    server.listen(5)

    print("[LDAP] SQL-to-LDAP Gateway started on 127.0.0.1:3893")

    while True:
        client, addr = server.accept()
        print(f"[LDAP] Client connected: {addr}")
        handle_client(client)

if __name__ == '__main__':
    main()
