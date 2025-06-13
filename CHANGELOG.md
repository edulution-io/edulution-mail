# Changelog - Edulution Mail

## [Unreleased] - 2025-01-06

### Fixed

#### Fix Docker volume mount issue for SOGo theme files
- Move docker-compose.override.yml creation from init() to apply_templates()
- Theme files are now copied before being referenced in override file
- Prevents Docker from creating directories instead of mounting files
- **Changed**: `build/entrypoint.sh`
  - Removed lines 65-85 from init() function
  - Added lines 96-114 to apply_templates() function

#### Fix Mailcow API activation timing issue  
- Move set_mailcow_token() call after mailcow startup
- Add MySQL readiness check before API token insertion
- Use INSERT IGNORE to prevent duplicate key errors
- **Changed**: `build/entrypoint.sh`
  - Moved set_mailcow_token call from line 142 to line 149
  - Added MySQL readiness check on lines 24-33
  - Added error handling for API token database insertion