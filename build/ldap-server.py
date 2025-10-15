#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL-to-LDAP Bridge for SOGo Group Expansion
Loads users and groups dynamically from MySQL edulution_gal table

PERFORMANCE NOTES for large deployments (2000+ users):
- Recommended SQL index: CREATE INDEX idx_edulution_gal_lookup ON edulution_gal(isGroup, mail);
- Memory usage: ~1.5 KB per user, ~2 KB per group (~3.5 MB for 2000 users)
- Tree rebuild: ~150-700ms every 60 seconds (acceptable)
- LDAP queries: Async/non-blocking (handles concurrent requests well)
"""
import logging
import os
import time
import mysql.connector
from twisted.internet import reactor, task
from twisted.internet.protocol import Factory
from ldaptor.inmemory import ReadOnlyInMemoryLDAPEntry
from ldaptor.protocols.ldap.ldapserver import LDAPServer
from ldaptor.interfaces import IConnectedLDAPEntry
from zope.interface import implementer

# ------------------------------------------------------------
# LOGGING SETUP
# ------------------------------------------------------------
LDAP_DEBUG = os.getenv('LDAP_DEBUG', 'false').lower() == 'true'

logging.basicConfig(
    level=logging.DEBUG if LDAP_DEBUG else logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("ldap-sql-bridge")

# ------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------
DB_CONFIG = {
    'unix_socket': '/var/run/mysqld/mysqld.sock',
    'user': os.getenv('DBUSER', 'mailcow'),
    'password': os.getenv('DBPASS', ''),
    'database': os.getenv('DBNAME', 'mailcow')
}

# Global LDAP tree
ldap_root = None

# ------------------------------------------------------------
# BUILD LDAP TREE FROM MYSQL
# ------------------------------------------------------------
def build_ldap_tree_from_sql():
    """Query MySQL edulution_gal and build LDAP tree"""
    global ldap_root

    start_time = time.time()

    try:
        # Connect to MySQL
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor(dictionary=True)

        # Get all users (isGroup IS NULL or isGroup = 0)
        if LDAP_DEBUG:
            logger.debug("Querying users from edulution_gal...")
        query_start = time.time()
        cursor.execute("""
            SELECT c_uid, c_cn, c_name, mail
            FROM edulution_gal
            WHERE (isGroup IS NULL OR isGroup = 0)
            AND mail IS NOT NULL
            ORDER BY c_uid
        """)
        users = cursor.fetchall()
        query_time = (time.time() - query_start) * 1000
        logger.info(f"✓ Loaded {len(users)} users from SQL ({query_time:.1f}ms)")

        # Log sample users (only in debug mode)
        if LDAP_DEBUG:
            for i, user in enumerate(users[:5]):
                logger.debug(f"  User sample {i+1}: uid={user['c_uid']}, cn={user.get('c_cn', 'N/A')}, mail={user['mail']}")
            if len(users) > 5:
                logger.debug(f"  ... and {len(users) - 5} more users")

        # Create email -> c_uid lookup map
        email_to_uid = {}
        for user in users:
            email_to_uid[user['mail']] = user['c_uid']
            # Also map c_uid to itself for flexibility
            email_to_uid[user['c_uid']] = user['c_uid']

        # Get all groups (isGroup = 1)
        if LDAP_DEBUG:
            logger.debug("Querying groups from edulution_gal...")
        query_start = time.time()
        cursor.execute("""
            SELECT c_uid, c_cn, mail, groupMembers
            FROM edulution_gal
            WHERE isGroup = 1
            AND mail IS NOT NULL
            ORDER BY c_uid
        """)
        groups = cursor.fetchall()
        query_time = (time.time() - query_start) * 1000
        logger.info(f"✓ Loaded {len(groups)} groups from SQL ({query_time:.1f}ms)")

        # Log ALL groups with member details (only in debug mode)
        if LDAP_DEBUG:
            for i, group in enumerate(groups):
                members_str = group.get('groupMembers', '') or ''
                member_list = members_str.strip().split() if members_str else []
                display_name = group.get('c_cn') or group['c_uid']
                logger.debug(f"  Group {i+1}: id={group['c_uid']}, name='{display_name}', mail={group['mail']}, members={len(member_list)}")
                if member_list:
                    logger.debug(f"    → Members: {', '.join(member_list[:10])}{'...' if len(member_list) > 10 else ''}")

        cursor.close()
        db.close()

        # Build LDAP tree
        root = ReadOnlyInMemoryLDAPEntry(
            dn=b"dc=schule,dc=lan",
            attributes={
                b"objectClass": [b"domain"],
                b"dc": [b"schule"]
            },
        )

        # Create OUs
        ou_users = ReadOnlyInMemoryLDAPEntry(
            dn=b"ou=users,dc=schule,dc=lan",
            attributes={
                b"objectClass": [b"organizationalUnit"],
                b"ou": [b"users"]
            }
        )

        ou_groups = ReadOnlyInMemoryLDAPEntry(
            dn=b"ou=groups,dc=schule,dc=lan",
            attributes={
                b"objectClass": [b"organizationalUnit"],
                b"ou": [b"groups"]
            }
        )

        # Add users
        user_entries = {}
        for user in users:
            uid = user['c_uid']
            cn = user.get('c_cn') or uid
            mail = user['mail']

            # Extract first/last name from c_cn
            if ' ' in cn:
                parts = cn.split(maxsplit=1)
                givenname = parts[0]
                sn = parts[1] if len(parts) > 1 else parts[0]
            else:
                givenname = cn
                sn = cn

            dn_str = f"uid={uid},ou=users,dc=schule,dc=lan"
            dn_bytes = dn_str.encode('utf-8')

            entry = ReadOnlyInMemoryLDAPEntry(
                dn=dn_bytes,
                attributes={
                    b"objectClass": [b"inetOrgPerson", b"person", b"top"],
                    b"uid": [uid.encode('utf-8')],
                    b"cn": [cn.encode('utf-8')],
                    b"sn": [sn.encode('utf-8')],
                    b"givenName": [givenname.encode('utf-8')],
                    b"mail": [mail.encode('utf-8')],
                },
            )

            rdn = f"uid={uid}".encode('utf-8')
            user_entries[rdn] = entry

        ou_users._children = user_entries

        # Add groups
        group_entries = {}
        for group in groups:
            group_id = group['c_uid']  # e.g., "p_cgs-edu3@linuxmuster.lan"
            display_name = group.get('c_cn') or group_id  # Display name for logging
            mail = group['mail']
            members_str = group.get('groupMembers') or ''

            # Parse members (space-separated emails)
            member_emails = members_str.strip().split() if members_str else []

            # Build uniqueMember DNs by looking up users
            unique_members = []
            for member_email in member_emails:
                # Resolve email to c_uid
                resolved_uid = email_to_uid.get(member_email)
                if resolved_uid:
                    member_dn = f"uid={resolved_uid},ou=users,dc=schule,dc=lan"
                    unique_members.append(member_dn.encode('utf-8'))
                else:
                    # User not found - log warning but continue
                    if LDAP_DEBUG:
                        logger.warning(f"Group {group_id}: Member {member_email} not found in users")

            # If no members, add dummy member (LDAP requires at least one)
            if not unique_members:
                unique_members = [b"cn=nobody,ou=users,dc=schule,dc=lan"]

            # IMPORTANT: cn in DN must match cn attribute value!
            # Use group_id (email without domain) as cn, just like the old static version
            # Extract local part from email for cleaner cn (e.g., "p_cgs-edu3" from "p_cgs-edu3@linuxmuster.lan")
            cn_value = group_id.split('@')[0] if '@' in group_id else group_id

            dn_str = f"cn={cn_value},ou=groups,dc=schule,dc=lan"
            dn_bytes = dn_str.encode('utf-8')

            entry = ReadOnlyInMemoryLDAPEntry(
                dn=dn_bytes,
                attributes={
                    b"objectClass": [b"groupOfUniqueNames", b"top", b"extensibleObject"],
                    b"cn": [cn_value.encode('utf-8')],  # MUST match cn in DN
                    b"mail": [mail.encode('utf-8')],
                    b"uniqueMember": unique_members,
                    b"structuralObjectClass": [b"groupOfUniqueNames"],
                },
            )

            rdn = f"cn={cn_value}".encode('utf-8')
            group_entries[rdn] = entry

        ou_groups._children = group_entries

        # Build tree
        root._children = {
            b"ou=users": ou_users,
            b"ou=groups": ou_groups
        }

        ldap_root = root
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ LDAP tree rebuilt: {len(user_entries)} users, {len(group_entries)} groups ({total_time:.1f}ms total)")

        return root

    except Exception as e:
        logger.error(f"Failed to build LDAP tree from SQL: {e}")
        # Return minimal tree on error
        if ldap_root:
            return ldap_root
        else:
            # Create empty tree as fallback
            root = ReadOnlyInMemoryLDAPEntry(
                dn=b"dc=schule,dc=lan",
                attributes={b"objectClass": [b"domain"], b"dc": [b"schule"]}
            )
            return root

# ------------------------------------------------------------
# FACTORY / SERVER IMPLEMENTATION
# ------------------------------------------------------------
@implementer(IConnectedLDAPEntry)
class InMemoryLDAPFactory(Factory):
    def __init__(self):
        self.root = None
        self.update_tree()

    def update_tree(self):
        """Rebuild LDAP tree from SQL"""
        self.root = build_ldap_tree_from_sql()

    def buildProtocol(self, addr):
        proto = LDAPServer()
        proto.factory = self

        # Hook search handler to log all incoming requests (only in debug mode)
        if LDAP_DEBUG:
            original = proto.handle_LDAPSearchRequest

            def logged_search(request, *args, **kwargs):
                try:
                    base = request.baseObject.decode("utf-8", "ignore")
                except Exception:
                    base = str(request.baseObject)

                scope_map = {0: "BASE", 1: "ONELEVEL", 2: "SUBTREE"}
                scope = scope_map.get(getattr(request, "scope", None), "?")

                logger.debug(f"SEARCH base='{base}' scope={scope}")
                return original(request, *args, **kwargs)

            proto.handle_LDAPSearchRequest = logged_search
        return proto

    def __conform__(self, interface):
        if interface is IConnectedLDAPEntry:
            return self.root
        return None

# ------------------------------------------------------------
# START SERVER
# ------------------------------------------------------------
if __name__ == '__main__':
    factory = InMemoryLDAPFactory()

    # Rebuild tree every 60 seconds to pick up SQL changes
    refresh_task = task.LoopingCall(factory.update_tree)
    refresh_task.start(60.0, now=False)

    reactor.listenTCP(3890, factory)

    logger.info("=" * 60)
    logger.info("SQL-to-LDAP Bridge Started")
    logger.info("LDAP URL: ldap://127.0.0.1:3890")
    logger.info("Data source: MySQL edulution_gal table")
    logger.info("Refresh interval: 60 seconds")
    logger.info(f"Debug logging: {'ENABLED' if LDAP_DEBUG else 'DISABLED'}")
    logger.info("=" * 60)

    reactor.run()
