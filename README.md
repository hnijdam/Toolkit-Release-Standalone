# ICY Toolkit (Clean Release)

This folder contains a cleaned, shareable version of the Support ICY Toolkit with the Bridge scripts and DB menu, ready for GitHub.

## Contents
- toolkit.ps1 / toolkit.bat: PowerShell launcher and menu
- Bridge TX/: Bridge Comlog viewer scripts
- python/DBscript/: DB menu and helpers
- Nodejs 4850cm database tools/: Node.js DB tools

## Requirements
- Windows 10/11
- PowerShell 7 (pwsh)
- Python 3.10+ (venv recommended)
- Node.js 18+ (for the Node tools)

## Install
1. Create a Python venv (recommended):
   - `python -m venv .venv`
   - Activate:
     - PowerShell: `.\.venv\Scripts\Activate.ps1`
2. Install Python dependencies:
   - `pip install -r python/DBscript/requirements.txt`
3. Install Node dependencies:
   - `cd "Nodejs 4850cm database tools"`
   - `npm install`
4. Configure DB credentials:
   - Copy `python/DBscript/.env.example` to `python/DBscript/.env` and fill values.

## Run
- `toolkit.bat` (recommended)
- or `pwsh -NoProfile -ExecutionPolicy Bypass -File .\toolkit.ps1`

## Output
- Log exports: `%USERPROFILE%\Documents\ICY-Logs`
- Bridge Comlog outputs: `%USERPROFILE%\Documents\ICY-Logs`

## Notes
- Update `toolkit.ps1` with your SSH key path and server list.
- Credentials should only live in `.env` and never be committed.
