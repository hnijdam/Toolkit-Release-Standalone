p = r"c:\Users\h.nijdam\OneDrive - I.C.Y. B.V\Scripts\python\DBscript\list_bridges_prompt.py"
with open(p, 'rb') as f:
    s = f.read().decode('utf-8', 'replace')
print('count """ ->', s.count('"""'))
print("count ''' ->", s.count("'''"))
lines = s.splitlines()
start = 600
end = 660
for i in range(start, min(end, len(lines))):
    print(i+1, lines[i])
print('\nLines containing triple quotes:')
for i,l in enumerate(lines):
     if '"""' in l or "'''" in l:
          print(i+1, l)
