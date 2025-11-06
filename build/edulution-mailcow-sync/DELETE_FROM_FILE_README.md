# Delete from File - Documentation

## Overview

The `delete_from_file.py` script allows you to delete multiple mailboxes and aliases from Mailcow using a simple text file containing email addresses.

## Features

- ✅ Delete mailboxes and aliases in bulk
- ✅ Automatic detection of mailbox vs alias
- ✅ Respects `IGNORE_MAILBOXES` configuration
- ✅ Safety confirmation prompt (can be skipped with `--force`)
- ✅ Detailed logging and statistics
- ✅ Comments and empty lines support in input file
- ✅ Error handling and validation

## File Format

Create a text file with one email address per line:

```txt
# This is a comment - lines starting with # are ignored
user1@example.com
user2@example.com

# Empty lines are also ignored
alias@example.com
olduser@example.com
```

## Usage

### Basic Usage (with confirmation prompt)

```bash
docker exec edulution-mail /app/venv/bin/python3 /app/delete_from_file.py /srv/docker/edulution-mail/delete_list.txt
```

### Force Mode (skip confirmation - USE WITH CAUTION!)

```bash
docker exec edulution-mail /app/venv/bin/python3 /app/delete_from_file.py /srv/docker/edulution-mail/delete_list.txt --force
```

### Help

```bash
docker exec edulution-mail /app/venv/bin/python3 /app/delete_from_file.py --help
```

## Workflow Example

### 1. Create your deletion list on the host

```bash
# On the host machine
cat > /srv/docker/edulution-mail/delete_list.txt << EOF
# Users to delete
olduser1@school.edu
olduser2@school.edu

# Aliases to delete
oldalias@school.edu
EOF
```

### 2. Review what will be deleted (dry-run)

The script will show you a summary before deleting anything:

```bash
docker exec edulution-mail /app/venv/bin/python3 /app/delete_from_file.py /srv/docker/edulution-mail/delete_list.txt
```

Output:
```
======================================================================
DELETION SUMMARY
======================================================================
Total addresses in file: 3
Mailboxes to delete: 2
Aliases to delete: 1
Not found (will be skipped): 0
Ignored (IGNORE_MAILBOXES): 0
======================================================================

Mailboxes:
  - olduser1@school.edu
  - olduser2@school.edu

Aliases:
  - oldalias@school.edu

======================================================================
Do you want to proceed with deletion? (yes/no):
```

### 3. Confirm and delete

Type `yes` to proceed, or `no` to cancel.

### 4. Check the results

```
======================================================================
DELETION COMPLETED
======================================================================
Mailboxes deleted: 2/2
Aliases deleted: 1/1
Not found: 0
Skipped (IGNORE_MAILBOXES): 0
Errors: 0
======================================================================
```

## Safety Features

### 1. IGNORE_MAILBOXES Protection

Addresses in your `IGNORE_MAILBOXES` configuration will be automatically skipped:

```
WARNING: SKIPPED (in IGNORE_MAILBOXES): admin@school.edu
```

### 2. Not Found = Skip

If an address doesn't exist in Mailcow, it will be skipped (not an error):

```
Not found:
  - nonexistent@school.edu
```

### 3. Confirmation Prompt

By default, you must confirm before deletion. Use `--force` only in automated scripts.

## Error Handling

The script will:
- ✅ Validate email format
- ✅ Check if file exists
- ✅ Handle network errors gracefully
- ✅ Report errors without stopping the whole process
- ✅ Exit with error code if any deletions fail

## Exit Codes

- `0` - Success
- `1` - Errors occurred during deletion
- `130` - User cancelled (Ctrl+C)

## Integration with Automation

### Example: Automated cleanup script

```bash
#!/bin/bash

# Create deletion list
echo "user1@example.com" > /tmp/to_delete.txt
echo "user2@example.com" >> /tmp/to_delete.txt

# Copy to container accessible location
cp /tmp/to_delete.txt /srv/docker/edulution-mail/

# Delete with force mode (no prompt)
docker exec edulution-mail /app/venv/bin/python3 /app/delete_from_file.py \
    /srv/docker/edulution-mail/to_delete.txt --force

# Check exit code
if [ $? -eq 0 ]; then
    echo "Deletion successful"
    rm /srv/docker/edulution-mail/to_delete.txt
else
    echo "Deletion failed!"
    exit 1
fi
```

## Troubleshooting

### "File not found"
- Ensure the file path is accessible from inside the container
- Use absolute paths
- The path must be inside the container filesystem or a mounted volume

### "Invalid email address format"
- Check that each line contains a valid email address with `@`
- Remove any extra spaces or special characters

### "Failed to delete"
- Check Mailcow logs for API errors
- Verify `MAILCOW_API_TOKEN` is valid
- Ensure Mailcow API is accessible from the container

## Best Practices

1. **Always test without `--force` first** to review what will be deleted
2. **Keep backups** before bulk deletion operations
3. **Use comments** in your deletion file to document why addresses are being deleted
4. **Check IGNORE_MAILBOXES** to protect important accounts
5. **Review logs** after deletion to ensure success

## See Also

- Main sync documentation
- Mailcow API documentation
- `IGNORE_MAILBOXES` configuration
