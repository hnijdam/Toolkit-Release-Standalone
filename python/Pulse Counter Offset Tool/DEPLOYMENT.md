# Deployment Guide

## Requirements
- Windows 10 or 11
- PowerShell
- Python 3.10+
- Network access to the ICY database host

## Local installation
1. Open this folder in Explorer or VS Code
2. Copy `.env.example` to `.env`
3. Fill in at least:
   - `DB_HOST`
   - `DB_USER`
   - `DB_PASSWORD`
   - `DB_NAME`
   - `USER_INITIALS`
4. Start `start_standalone.bat`
5. The script creates a local `.venv` automatically and installs dependencies
6. Your browser opens once the Streamlit app is ready

## Manual start
If needed, you can also run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_standalone.ps1
```

## Notes
- Real credentials are not stored in Git
- `.env` is local-only
- `.venv` is local-only
- The app binds to `127.0.0.1`

## Publish only this tool to GitHub
From the main Toolkit repository, use:

```powershell
git subtree split --prefix="python/Pulse Counter Offset Tool" -b pulse-counter-standalone
git push https://github.com/hnijdam/Pulse-Counter-stand-alone.git pulse-counter-standalone:main --force
```

This publishes only the standalone Pulse Counter tool and not the rest of the Toolkit.
