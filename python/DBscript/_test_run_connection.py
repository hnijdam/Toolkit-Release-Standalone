import os
import sys
import types
import runpy

# Ensure venv imports won't prompt for credentials
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_HOST', 'dummy')
os.environ.setdefault('DB_HOST2', '')

# Create a fake mysql.connector in sys.modules before importing the script
mysql = types.ModuleType('mysql')
connector = types.ModuleType('mysql.connector')

class Error(Exception):
    pass

class FakeCursor:
    def close(self):
        pass
    def execute(self, *a, **k):
        pass
    def fetchall(self):
        return []
    @property
    def description(self):
        return None

class FakeConn:
    def is_connected(self):
        return True
    def cursor(self, *a, **k):
        return FakeCursor()
    def close(self):
        pass

def connect(*a, **k):
    return FakeConn()

connector.connect = connect
connector.Error = Error
mysql.connector = connector
sys.modules['mysql'] = mysql
sys.modules['mysql.connector'] = connector

# Run the target script by path; pass CLI args to trigger a list operation
script_path = r"c:\Users\h.nijdam\OneDrive - I.C.Y. B.V\Scripts\python\DBscript\list_bridges_prompt.py"
sys.argv = [script_path, '--db', 'somedb', '--action', 'list']
print('--- Running test runner: executing script ---')
runpy.run_path(script_path, run_name='__main__')
print('--- Test run complete ---')
