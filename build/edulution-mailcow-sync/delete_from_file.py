#!/usr/bin/env python3

import sys
import os
import logging
import argparse
from modules import Mailcow, ConfigurationStorage

logging.basicConfig(format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)

class DeleteFromFile:
    """
    CLI tool to delete mailboxes and aliases from a file containing email addresses.

    Usage:
        python3 delete_from_file.py /path/to/file.txt [--force]

    File format:
        - One email address per line
        - Lines starting with # are treated as comments
        - Empty lines are ignored
    """

    def __init__(self):
        self._config = self._readConfig()
        self.mailcow = Mailcow(apiToken=self._config.MAILCOW_API_TOKEN)

    def _readConfig(self) -> ConfigurationStorage:
        config = ConfigurationStorage()
        config.load()
        return config

    def read_addresses_from_file(self, file_path: str) -> list:
        """Read email addresses from file (one per line)"""
        addresses = []

        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            return addresses

        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Basic email validation
                    if '@' not in line:
                        logging.warning(f"Line {line_num}: Invalid email address format: {line}")
                        continue

                    addresses.append(line)

            logging.info(f"Read {len(addresses)} addresses from file: {file_path}")
            return addresses

        except Exception as e:
            logging.error(f"Error reading file: {e}")
            return []

    def check_if_mailbox_exists(self, address: str) -> bool:
        """Check if address is a mailbox"""
        try:
            mailboxes = self.mailcow.getMailboxes()
            if mailboxes:
                for mailbox in mailboxes:
                    if mailbox.get('username') == address:
                        return True
        except Exception as e:
            logging.error(f"Error checking mailbox {address}: {e}")
        return False

    def check_if_alias_exists(self, address: str) -> dict:
        """Check if address is an alias and return alias data"""
        try:
            aliases = self.mailcow.getAliases()
            if aliases:
                for alias in aliases:
                    if alias.get('address') == address:
                        return alias
        except Exception as e:
            logging.error(f"Error checking alias {address}: {e}")
        return None

    def delete_addresses(self, addresses: list, force: bool = False) -> dict:
        """
        Delete mailboxes and aliases from the list
        Returns statistics about the operation
        """
        stats = {
            'total': len(addresses),
            'mailboxes_deleted': 0,
            'aliases_deleted': 0,
            'not_found': 0,
            'errors': 0,
            'skipped': []
        }

        # Check what we're about to delete
        mailboxes_to_delete = []
        aliases_to_delete = []
        not_found = []

        logging.info("Analyzing addresses...")
        for address in addresses:
            # Check if it's in IGNORE list
            if address in self._config.IGNORE_MAILBOXES:
                logging.warning(f"SKIPPED (in IGNORE_MAILBOXES): {address}")
                stats['skipped'].append(address)
                continue

            # Check if it's a mailbox
            if self.check_if_mailbox_exists(address):
                mailboxes_to_delete.append(address)
            # Check if it's an alias
            elif self.check_if_alias_exists(address):
                aliases_to_delete.append(address)
            else:
                not_found.append(address)

        # Print summary
        logging.info("")
        logging.info("=" * 70)
        logging.info("DELETION SUMMARY")
        logging.info("=" * 70)
        logging.info(f"Total addresses in file: {stats['total']}")
        logging.info(f"Mailboxes to delete: {len(mailboxes_to_delete)}")
        logging.info(f"Aliases to delete: {len(aliases_to_delete)}")
        logging.info(f"Not found (will be skipped): {len(not_found)}")
        logging.info(f"Ignored (IGNORE_MAILBOXES): {len(stats['skipped'])}")
        logging.info("=" * 70)

        if mailboxes_to_delete:
            logging.info("\nMailboxes:")
            for mb in mailboxes_to_delete:
                logging.info(f"  - {mb}")

        if aliases_to_delete:
            logging.info("\nAliases:")
            for alias in aliases_to_delete:
                logging.info(f"  - {alias}")

        if not_found:
            logging.info("\nNot found:")
            for nf in not_found:
                logging.info(f"  - {nf}")

        if stats['skipped']:
            logging.info("\nSkipped (IGNORE_MAILBOXES):")
            for skipped in stats['skipped']:
                logging.info(f"  - {skipped}")

        logging.info("=" * 70)

        # Ask for confirmation unless --force is used
        if not force:
            logging.info("")
            response = input("Do you want to proceed with deletion? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                logging.info("Deletion cancelled by user.")
                return stats

        # Perform deletion
        logging.info("")
        logging.info("Starting deletion...")

        # Delete mailboxes
        for mailbox in mailboxes_to_delete:
            try:
                if self.mailcow.deleteMailbox(mailbox):
                    stats['mailboxes_deleted'] += 1
                    logging.info(f"✓ Deleted mailbox: {mailbox}")
                else:
                    stats['errors'] += 1
                    logging.error(f"✗ Failed to delete mailbox: {mailbox}")
            except Exception as e:
                stats['errors'] += 1
                logging.error(f"✗ Error deleting mailbox {mailbox}: {e}")

        # Delete aliases
        for alias in aliases_to_delete:
            try:
                if self.mailcow.deleteAlias(alias):
                    stats['aliases_deleted'] += 1
                    logging.info(f"✓ Deleted alias: {alias}")
                else:
                    stats['errors'] += 1
                    logging.error(f"✗ Failed to delete alias: {alias}")
            except Exception as e:
                stats['errors'] += 1
                logging.error(f"✗ Error deleting alias {alias}: {e}")

        stats['not_found'] = len(not_found)

        # Final summary
        logging.info("")
        logging.info("=" * 70)
        logging.info("DELETION COMPLETED")
        logging.info("=" * 70)
        logging.info(f"Mailboxes deleted: {stats['mailboxes_deleted']}/{len(mailboxes_to_delete)}")
        logging.info(f"Aliases deleted: {stats['aliases_deleted']}/{len(aliases_to_delete)}")
        logging.info(f"Not found: {stats['not_found']}")
        logging.info(f"Skipped (IGNORE_MAILBOXES): {len(stats['skipped'])}")
        logging.info(f"Errors: {stats['errors']}")
        logging.info("=" * 70)

        return stats


def main():
    parser = argparse.ArgumentParser(
        description='Delete mailboxes and aliases from a file',
        epilog="""
File format:
  - One email address per line
  - Lines starting with # are comments
  - Empty lines are ignored

Example:
  # Delete these accounts
  user1@example.com
  user2@example.com
  alias@example.com

Usage:
  # With confirmation prompt
  python3 delete_from_file.py /path/to/addresses.txt

  # Skip confirmation (dangerous!)
  python3 delete_from_file.py /path/to/addresses.txt --force

  # Inside Docker container
  docker exec edulution-mail python3 /sync/delete_from_file.py /srv/docker/edulution-mail/delete_list.txt
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('file', help='Path to file containing email addresses (one per line)')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Skip confirmation prompt (USE WITH CAUTION!)')

    args = parser.parse_args()

    # Validate file path
    if not os.path.exists(args.file):
        logging.error(f"File not found: {args.file}")
        sys.exit(1)

    logging.info("=" * 70)
    logging.info("EDULUTION MAILCOW - DELETE FROM FILE")
    logging.info("=" * 70)
    logging.info(f"File: {args.file}")
    logging.info(f"Force mode: {args.force}")
    logging.info("=" * 70)
    logging.info("")

    try:
        deleter = DeleteFromFile()
        addresses = deleter.read_addresses_from_file(args.file)

        if not addresses:
            logging.warning("No valid addresses found in file.")
            sys.exit(0)

        stats = deleter.delete_addresses(addresses, force=args.force)

        # Exit with error code if there were errors
        if stats['errors'] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logging.info("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
