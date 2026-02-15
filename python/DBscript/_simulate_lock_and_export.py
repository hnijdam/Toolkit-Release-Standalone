import os
import stat
from pathlib import Path
import pandas as pd

import list_bridges_prompt as lbp


def make_readonly(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"Locked placeholder")
    try:
        os.chmod(p, stat.S_IREAD)
    except Exception:
        # best-effort; on some Windows setups, this may not fully lock the file
        pass


def clear_readonly(p: Path):
    try:
        os.chmod(p, stat.S_IWRITE)
    except Exception:
        pass


def main():
    export_dir = Path(r"C:/Users/h.nijdam/Documents/ICY-Logs")
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / 'pollfail_combined.xlsx'

    # create a read-only placeholder to simulate a locked file
    if not target.exists():
        make_readonly(target)
    else:
        # ensure it's readonly
        try:
            os.chmod(target, stat.S_IREAD)
        except Exception:
            pass

    df = pd.DataFrame({'inbridgeid': [1, 2], 'hostname': ['a', 'b'], 'polling': [10, 5], 'pollfailure': [2, 3]})

    try:
        written = lbp._write_xlsx_with_fallback(target, df, sheet_name='PollFails')
        print('simulate: written ->', written)
    except Exception as e:
        print('simulate: error ->', e)
    finally:
        # restore write permission on original placeholder so user can delete/inspect
        clear_readonly(target)


if __name__ == '__main__':
    main()
