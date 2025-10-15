#!/usr/bin/env python3
"""
Minimal LDAP server that translates LDAP queries to SQL (edulution_gal)
Runs inside SOGo container via supervisord
"""

import socketserver
import struct
import mysql.connector
import os
import sys

# LDAP Protocol constants
LDAP_BIND_REQUEST = 0x60
LDAP_BIND_RESPONSE = 0x61
LDAP_SEARCH_REQUEST = 0x63
LDAP_SEARCH_RESULT_ENTRY = 0x64
LDAP_SEARCH_RESULT_DONE = 0x65

class LDAPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            data = self.request.recv(4096)
            if not data:
                return

            # Simple LDAP message parsing
            # Format: 0x30 (SEQUENCE) + length + messageID + operation

            if len(data) < 6:
                return

            msg_type = data[5] if len(data) > 5 else 0

            if msg_type == LDAP_BIND_REQUEST:
                # Bind always succeeds
                response = self.create_bind_response()
                self.request.sendall(response)

            elif msg_type == LDAP_SEARCH_REQUEST:
                # Parse search and query SQL
                response = self.handle_search(data)
                self.request.sendall(response)

        except Exception as e:
            print(f"[LDAP] Error: {e}", file=sys.stderr)

    def create_bind_response(self):
        """Create LDAP BindResponse (success)"""
        # Simplified LDAP BindResponse
        # 0x30 = SEQUENCE
        # 0x61 = BindResponse
        # 0x0a = INTEGER (resultCode)
        # 0x00 = success
        return bytes([
            0x30, 0x0c,  # SEQUENCE, length 12
            0x02, 0x01, 0x01,  # messageID = 1
            0x61, 0x07,  # BindResponse, length 7
            0x0a, 0x01, 0x00,  # resultCode = 0 (success)
            0x04, 0x00,  # matchedDN (empty)
            0x04, 0x00   # diagnosticMessage (empty)
        ])

    def handle_search(self, data):
        """Handle LDAP search request"""
        # Extract search parameters (simplified parsing)
        # In real implementation, parse ASN.1 properly

        data_str = data.decode('latin1', errors='ignore')

        # Try to extract CN from filter
        cn = None
        if 'cn=' in data_str:
            try:
                start = data_str.index('cn=') + 3
                end = data_str.find(')', start)
                if end == -1:
                    end = data_str.find('\x00', start)
                cn = data_str[start:end] if end > start else None
            except:
                pass

        if cn:
            return self.query_group_members(cn)

        return self.create_search_done()

    def query_group_members(self, group_cn):
        """Query MySQL for group members"""
        try:
            db = mysql.connector.connect(
                unix_socket='/var/run/mysqld/mysqld.sock',
                user=os.getenv('DBUSER', 'mailcow'),
                password=os.getenv('DBPASS', ''),
                database=os.getenv('DBNAME', 'mailcow')
            )
            cursor = db.cursor(dictionary=True)

            # Get group
            cursor.execute("""
                SELECT c_uid, groupMembers, isGroup
                FROM edulution_gal
                WHERE c_uid = %s AND isGroup = 1
            """, (group_cn,))

            group = cursor.fetchone()
            if not group or not group['groupMembers']:
                return self.create_search_done()

            # Get members
            member_emails = group['groupMembers'].split()
            if not member_emails:
                return self.create_search_done()

            placeholders = ','.join(['%s'] * len(member_emails))
            cursor.execute(f"""
                SELECT c_uid, c_cn, mail, c_givenname, c_sn
                FROM edulution_gal
                WHERE c_uid IN ({placeholders}) OR mail IN ({placeholders})
            """, member_emails + member_emails)

            members = cursor.fetchall()
            cursor.close()
            db.close()

            # Create LDAP response with members
            return self.create_member_entries(members) + self.create_search_done()

        except Exception as e:
            print(f"[LDAP] SQL error: {e}", file=sys.stderr)
            return self.create_search_done()

    def create_member_entries(self, members):
        """Create LDAP SearchResultEntry for each member"""
        # Simplified - return minimal valid LDAP entries
        # Real implementation would use proper ASN.1 encoding
        entries = b''

        for member in members:
            dn = f"cn={member['c_uid']},ou=users,dc=edulution,dc=local"
            mail = member['mail'] or member['c_uid']

            # Minimal LDAP SearchResultEntry
            # This is highly simplified - proper LDAP encoding needed
            entry = bytes([
                0x30, 0x50,  # SEQUENCE
                0x02, 0x01, 0x02,  # messageID
                0x64, 0x4b,  # SearchResultEntry
            ])
            # Add DN and attributes (simplified)
            entries += entry

        return entries

    def create_search_done(self):
        """Create LDAP SearchResultDone"""
        return bytes([
            0x30, 0x0c,  # SEQUENCE
            0x02, 0x01, 0x02,  # messageID = 2
            0x65, 0x07,  # SearchResultDone
            0x0a, 0x01, 0x00,  # resultCode = 0 (success)
            0x04, 0x00,  # matchedDN
            0x04, 0x00   # diagnosticMessage
        ])

if __name__ == '__main__':
    HOST, PORT = '127.0.0.1', 3893

    print(f"[LDAP] Starting SQL-to-LDAP bridge on {HOST}:{PORT}")

    server = socketserver.TCPServer((HOST, PORT), LDAPHandler)
    server.allow_reuse_address = True

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[LDAP] Shutting down")
        server.shutdown()
