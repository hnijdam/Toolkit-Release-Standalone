# Security

## Credentials
- Do not commit real credentials.
- Use `python/DBscript/.env` for DB credentials.
- Keep SSH key paths local in `toolkit.ps1`.

## Safe Sharing Checklist
- Ensure `.env` is excluded from version control.
- Ensure SSH key paths and hostnames are placeholders before sharing.
- Remove any logs, exports, or generated HTML before publishing.
