
import os
import re

root = r'C:\D-pan\Dpanqianyi\Python-Project'
ignore = {'.git', '.claude', '.idea', '.vscode', '.codegraph', '__pycache__', 'node_modules'}

file_writes = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in ignore]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        rel = os.path.relpath(fp, root)
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    if re.search(r'open\([^,]+,\s*[\'"][wa\+]', line) or re.search(r'\.(to_csv|to_excel|write_text|write_bytes|savefig)\(', line):
                        file_writes.append((rel, i, line.strip()))
        except Exception as e:
            pass

print(f"Total file writing statements found: {len(file_writes)}")
with open('file_writes_audit.txt', 'w', encoding='utf-8') as out:
    for fw in file_writes:
        out.write(f"{fw[0]}:{fw[1]} -> {fw[2]}\n")

print("Wrote file_writes_audit.txt successfully")
