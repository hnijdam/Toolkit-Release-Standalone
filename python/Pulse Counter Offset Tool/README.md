# Pulse Counter Offset Tool

Standalone Streamlit tool for viewing pulse counter readings, adjusting offsets, and optionally updating the meter divider.

## Features
- direct database connection
- manual offset changes
- batch import via Excel or CSV
- meterdivider-aware calculations
- protection for MID-certified ICY4850 Campère meters

## Quick start
1. Install Python 3.10 or newer
2. Copy `.env.example` to `.env`
3. Fill in the database settings in `.env` or directly in the app
4. Start with `start_standalone.bat`

## Included files
- `pulse_counter_offset_tool.py`
- `start_standalone.ps1`
- `start_standalone.bat`
- `requirements.txt`
- `.env.example`
- `logo_icy.svg`

See `DEPLOYMENT.md` for full installation and GitHub publishing instructions.
