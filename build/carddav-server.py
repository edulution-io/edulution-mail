#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL-to-CardDAV Bridge for Global Address Books
Provides read-only CardDAV access to edulution_gal MySQL view

Endpoints:
  /carddav/users/     - All users and aliases
  /carddav/groups/    - All distribution lists/groups

Usage:
  Clients can connect via CardDAV to:
  https://mail.example.com/carddav/users/
  https://mail.example.com/carddav/groups/
"""

import logging
import os
import time
import uuid
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
import mysql.connector
from xml.etree import ElementTree as ET
from threading import Thread, Lock
import json

# ------------------------------------------------------------
# LOGGING SETUP
# ------------------------------------------------------------
CARDDAV_DEBUG = os.getenv('CARDDAV_DEBUG', 'true').lower() == 'true'

logging.basicConfig(
    level=logging.DEBUG if CARDDAV_DEBUG else logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("carddav-bridge")

# ------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------
DB_CONFIG = {
    'host': 'mysql',
    'user': os.getenv('DBUSER', 'mailcow'),
    'password': os.getenv('DBPASS', ''),
    'database': os.getenv('DBNAME', 'mailcow')
}

# Global cache for contacts
contacts_cache = {
    'users': [],
    'groups': [],
    'last_update': 0
}
cache_lock = Lock()
CACHE_TTL = 60  # Refresh every 60 seconds

# ------------------------------------------------------------
# DATABASE FUNCTIONS
# ------------------------------------------------------------
def load_contacts_from_sql():
    """Load all contacts from edulution_gal MySQL view"""
    global contacts_cache

    try:
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor(dictionary=True)

        # Load users
        cursor.execute("""
            SELECT c_uid, c_cn, c_name, mail, c_sn, c_givenname
            FROM edulution_gal
            WHERE (isGroup IS NULL OR isGroup = 0)
            AND mail IS NOT NULL
            ORDER BY c_cn
        """)
        users = cursor.fetchall()

        # Load groups
        cursor.execute("""
            SELECT c_uid, c_cn, mail, members
            FROM edulution_gal
            WHERE isGroup = 1
            ORDER BY c_cn
        """)
        groups = cursor.fetchall()

        cursor.close()
        db.close()

        with cache_lock:
            contacts_cache['users'] = users
            contacts_cache['groups'] = groups
            contacts_cache['last_update'] = time.time()

        logger.info(f"✓ Loaded {len(users)} users and {len(groups)} groups from SQL")

    except Exception as e:
        logger.error(f"Error loading contacts from SQL: {e}")

def refresh_cache_periodically():
    """Background thread to refresh contacts cache"""
    while True:
        time.sleep(CACHE_TTL)
        load_contacts_from_sql()

# ------------------------------------------------------------
# VCARD GENERATION
# ------------------------------------------------------------
def generate_vcard(contact, is_group=False):
    """Generate vCard 3.0 format for a contact"""

    uid = contact.get('c_uid', str(uuid.uuid4()))
    cn = contact.get('c_cn', 'Unknown')
    mail = contact.get('mail', '')

    if is_group:
        # vCard for group/distribution list
        vcard = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{uid}",
            f"FN:{cn}",
            f"N:{cn};;;;",
            "KIND:group",
            f"EMAIL;TYPE=INTERNET:{mail}",
        ]

        # Add members if available
        members = contact.get('members', '')
        if members:
            try:
                member_list = json.loads(members) if isinstance(members, str) else members
                for member_mail in member_list:
                    vcard.append(f"X-ADDRESSBOOKSERVER-MEMBER:mailto:{member_mail}")
            except:
                pass

        vcard.append("END:VCARD")

    else:
        # vCard for person
        sn = contact.get('c_sn', cn.split()[-1] if ' ' in cn else cn)
        givenname = contact.get('c_givenname', cn.split()[0] if ' ' in cn else '')

        vcard = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{uid}",
            f"FN:{cn}",
            f"N:{sn};{givenname};;;",
            f"EMAIL;TYPE=INTERNET:{mail}",
            "END:VCARD"
        ]

    return "\r\n".join(vcard) + "\r\n"

def get_etag(contact):
    """Generate ETag for a contact based on content hash"""
    content = f"{contact.get('c_uid')}{contact.get('c_cn')}{contact.get('mail')}"
    return hashlib.md5(content.encode()).hexdigest()

# ------------------------------------------------------------
# CARDDAV HTTP HANDLER
# ------------------------------------------------------------
class CardDAVHandler(BaseHTTPRequestHandler):
    """HTTP Handler for CardDAV requests"""

    def log_message(self, format, *args):
        """Override to use our logger"""
        if CARDDAV_DEBUG:
            logger.debug(f"{self.address_string()} - {format % args}")

    def do_OPTIONS(self):
        """Handle OPTIONS request"""
        self.send_response(200)
        self.send_header('DAV', '1, 2, 3, addressbook')
        self.send_header('Allow', 'OPTIONS, GET, HEAD, PROPFIND, REPORT')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'OPTIONS, GET, HEAD, PROPFIND, REPORT')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Depth, Prefer')
        self.end_headers()

    def do_PROPFIND(self):
        """Handle PROPFIND request (discover collections and resources)"""
        path = unquote(urlparse(self.path).path)
        depth = self.headers.get('Depth', '0')

        logger.info(f"PROPFIND {path} (Depth: {depth})")

        # Check cache freshness
        if time.time() - contacts_cache['last_update'] > CACHE_TTL:
            load_contacts_from_sql()

        # Determine collection
        is_users = '/users' in path
        is_groups = '/groups' in path
        is_root = path == '/carddav/' or path == '/carddav'

        # Root collection
        if is_root:
            response = self._build_root_propfind()
        # Users collection
        elif is_users:
            if path.endswith('.vcf'):
                response = self._build_contact_propfind(path, 'users')
            else:
                response = self._build_collection_propfind('users', depth)
        # Groups collection
        elif is_groups:
            if path.endswith('.vcf'):
                response = self._build_contact_propfind(path, 'groups')
            else:
                response = self._build_collection_propfind('groups', depth)
        else:
            self.send_error(404, "Not Found")
            return

        self.send_response(207, 'Multi-Status')
        self.send_header('Content-Type', 'application/xml; charset=utf-8')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def do_REPORT(self):
        """Handle REPORT request (sync collections, get contact data)"""
        path = unquote(urlparse(self.path).path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ''

        logger.info(f"REPORT {path}")
        if CARDDAV_DEBUG:
            logger.debug(f"REPORT body: {body[:500]}")

        # Check cache
        if time.time() - contacts_cache['last_update'] > CACHE_TTL:
            load_contacts_from_sql()

        is_users = '/users' in path
        is_groups = '/groups' in path

        if is_users or is_groups:
            collection = 'users' if is_users else 'groups'
            response = self._build_addressbook_multiget(collection, body)
        else:
            self.send_error(404, "Not Found")
            return

        self.send_response(207, 'Multi-Status')
        self.send_header('Content-Type', 'application/xml; charset=utf-8')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def do_GET(self):
        """Handle GET request (download vCard)"""
        path = unquote(urlparse(self.path).path)

        logger.info(f"GET {path}")

        # Check cache
        if time.time() - contacts_cache['last_update'] > CACHE_TTL:
            load_contacts_from_sql()

        # Extract contact UID from path
        if path.endswith('.vcf'):
            uid = path.split('/')[-1].replace('.vcf', '')
            is_users = '/users/' in path
            is_groups = '/groups/' in path

            if is_users:
                contact = next((c for c in contacts_cache['users'] if c['c_uid'] == uid), None)
                is_group = False
            elif is_groups:
                contact = next((c for c in contacts_cache['groups'] if c['c_uid'] == uid), None)
                is_group = True
            else:
                self.send_error(404, "Not Found")
                return

            if contact:
                vcard = generate_vcard(contact, is_group)
                etag = get_etag(contact)

                self.send_response(200)
                self.send_header('Content-Type', 'text/vcard; charset=utf-8')
                self.send_header('Content-Length', len(vcard))
                self.send_header('ETag', f'"{etag}"')
                self.end_headers()
                self.wfile.write(vcard.encode('utf-8'))
            else:
                self.send_error(404, "Contact Not Found")
        else:
            self.send_error(404, "Not Found")

    # ------------------------------------------------------------
    # RESPONSE BUILDERS
    # ------------------------------------------------------------
    def _build_root_propfind(self):
        """Build PROPFIND response for root collection"""
        multistatus = ET.Element('{DAV:}multistatus')
        multistatus.set('xmlns:D', 'DAV:')
        multistatus.set('xmlns:CARD', 'urn:ietf:params:xml:ns:carddav')

        # Root response
        response = ET.SubElement(multistatus, '{DAV:}response')
        ET.SubElement(response, '{DAV:}href').text = '/carddav/'

        propstat = ET.SubElement(response, '{DAV:}propstat')
        prop = ET.SubElement(propstat, '{DAV:}prop')
        ET.SubElement(prop, '{DAV:}displayname').text = 'Global Address Books'
        ET.SubElement(prop, '{DAV:}resourcetype').append(ET.Element('{DAV:}collection'))
        ET.SubElement(propstat, '{DAV:}status').text = 'HTTP/1.1 200 OK'

        return ET.tostring(multistatus, encoding='unicode')

    def _build_collection_propfind(self, collection, depth):
        """Build PROPFIND response for addressbook collection"""
        multistatus = ET.Element('{DAV:}multistatus')
        multistatus.set('xmlns:D', 'DAV:')
        multistatus.set('xmlns:CARD', 'urn:ietf:params:xml:ns:carddav')

        collection_name = 'Benutzer' if collection == 'users' else 'Gruppen'
        collection_path = f'/carddav/{collection}/'

        # Collection itself
        response = ET.SubElement(multistatus, '{DAV:}response')
        ET.SubElement(response, '{DAV:}href').text = collection_path

        propstat = ET.SubElement(response, '{DAV:}propstat')
        prop = ET.SubElement(propstat, '{DAV:}prop')
        ET.SubElement(prop, '{DAV:}displayname').text = f'GAL {collection_name}'
        resourcetype = ET.SubElement(prop, '{DAV:}resourcetype')
        resourcetype.append(ET.Element('{DAV:}collection'))
        resourcetype.append(ET.Element('{urn:ietf:params:xml:ns:carddav}addressbook'))
        ET.SubElement(prop, '{DAV:}getcontenttype').text = 'text/vcard'
        ET.SubElement(propstat, '{DAV:}status').text = 'HTTP/1.1 200 OK'

        # If depth > 0, include all contacts
        if depth != '0':
            contacts = contacts_cache[collection]
            is_group = (collection == 'groups')

            for contact in contacts:
                uid = contact['c_uid']
                cn = contact.get('c_cn', 'Unknown')

                contact_response = ET.SubElement(multistatus, '{DAV:}response')
                ET.SubElement(contact_response, '{DAV:}href').text = f'{collection_path}{uid}.vcf'

                contact_propstat = ET.SubElement(contact_response, '{DAV:}propstat')
                contact_prop = ET.SubElement(contact_propstat, '{DAV:}prop')
                ET.SubElement(contact_prop, '{DAV:}displayname').text = cn
                ET.SubElement(contact_prop, '{DAV:}getcontenttype').text = 'text/vcard; charset=utf-8'
                ET.SubElement(contact_prop, '{DAV:}getetag').text = f'"{get_etag(contact)}"'
                contact_resourcetype = ET.SubElement(contact_prop, '{DAV:}resourcetype')
                ET.SubElement(contact_propstat, '{DAV:}status').text = 'HTTP/1.1 200 OK'

        return ET.tostring(multistatus, encoding='unicode')

    def _build_contact_propfind(self, path, collection):
        """Build PROPFIND response for single contact"""
        uid = path.split('/')[-1].replace('.vcf', '')
        contacts = contacts_cache[collection]
        contact = next((c for c in contacts if c['c_uid'] == uid), None)

        if not contact:
            return self._build_error_response(404, "Not Found")

        multistatus = ET.Element('{DAV:}multistatus')
        multistatus.set('xmlns:D', 'DAV:')

        response = ET.SubElement(multistatus, '{DAV:}response')
        ET.SubElement(response, '{DAV:}href').text = path

        propstat = ET.SubElement(response, '{DAV:}propstat')
        prop = ET.SubElement(propstat, '{DAV:}prop')
        ET.SubElement(prop, '{DAV:}displayname').text = contact.get('c_cn', 'Unknown')
        ET.SubElement(prop, '{DAV:}getcontenttype').text = 'text/vcard; charset=utf-8'
        ET.SubElement(prop, '{DAV:}getetag').text = f'"{get_etag(contact)}"'
        ET.SubElement(prop, '{DAV:}resourcetype')
        ET.SubElement(propstat, '{DAV:}status').text = 'HTTP/1.1 200 OK'

        return ET.tostring(multistatus, encoding='unicode')

    def _build_addressbook_multiget(self, collection, body):
        """Build addressbook-multiget REPORT response"""
        multistatus = ET.Element('{DAV:}multistatus')
        multistatus.set('xmlns:D', 'DAV:')
        multistatus.set('xmlns:CARD', 'urn:ietf:params:xml:ns:carddav')

        contacts = contacts_cache[collection]
        is_group = (collection == 'groups')

        # Parse requested hrefs from body (if specific contacts requested)
        try:
            root = ET.fromstring(body)
            hrefs = [elem.text for elem in root.findall('.//{DAV:}href')]
        except:
            hrefs = []

        # If no specific hrefs, return all contacts
        if not hrefs:
            for contact in contacts:
                uid = contact['c_uid']
                response = ET.SubElement(multistatus, '{DAV:}response')
                ET.SubElement(response, '{DAV:}href').text = f'/carddav/{collection}/{uid}.vcf'

                propstat = ET.SubElement(response, '{DAV:}propstat')
                prop = ET.SubElement(propstat, '{DAV:}prop')
                ET.SubElement(prop, '{DAV:}getetag').text = f'"{get_etag(contact)}"'

                # Include vCard data
                vcard_data = generate_vcard(contact, is_group)
                ET.SubElement(prop, '{urn:ietf:params:xml:ns:carddav}address-data').text = vcard_data

                ET.SubElement(propstat, '{DAV:}status').text = 'HTTP/1.1 200 OK'
        else:
            # Return specific requested contacts
            for href in hrefs:
                uid = href.split('/')[-1].replace('.vcf', '')
                contact = next((c for c in contacts if c['c_uid'] == uid), None)

                if contact:
                    response = ET.SubElement(multistatus, '{DAV:}response')
                    ET.SubElement(response, '{DAV:}href').text = href

                    propstat = ET.SubElement(response, '{DAV:}propstat')
                    prop = ET.SubElement(propstat, '{DAV:}prop')
                    ET.SubElement(prop, '{DAV:}getetag').text = f'"{get_etag(contact)}"'

                    vcard_data = generate_vcard(contact, is_group)
                    ET.SubElement(prop, '{urn:ietf:params:xml:ns:carddav}address-data').text = vcard_data

                    ET.SubElement(propstat, '{DAV:}status').text = 'HTTP/1.1 200 OK'

        return ET.tostring(multistatus, encoding='unicode')

    def _build_error_response(self, code, message):
        """Build error response"""
        multistatus = ET.Element('{DAV:}multistatus')
        response = ET.SubElement(multistatus, '{DAV:}response')
        ET.SubElement(response, '{DAV:}status').text = f'HTTP/1.1 {code} {message}'
        return ET.tostring(multistatus, encoding='unicode')

# ------------------------------------------------------------
# SERVER STARTUP
# ------------------------------------------------------------
def run_server(port=8800):
    """Start CardDAV HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, CardDAVHandler)
    logger.info(f"CardDAV server listening on port {port}")
    logger.info("Endpoints:")
    logger.info("  /carddav/users/  - Benutzer (Users)")
    logger.info("  /carddav/groups/ - Gruppen (Distribution Lists)")
    httpd.serve_forever()

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("SQL-to-CardDAV Bridge for Global Address Books")
    logger.info("=" * 60)

    # Initial load
    load_contacts_from_sql()

    # Start background refresh thread
    refresh_thread = Thread(target=refresh_cache_periodically, daemon=True)
    refresh_thread.start()
    logger.info("✓ Background cache refresh enabled (60s interval)")

    # Start HTTP server
    try:
        run_server(port=8800)
    except KeyboardInterrupt:
        logger.info("\nShutting down CardDAV server...")
