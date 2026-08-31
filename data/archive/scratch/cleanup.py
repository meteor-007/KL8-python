import shutil, os
count = 0
for root, dirs, files in os.walk('.'):
    for d in dirs:
        if d == '__pycache__':
            path = os.path.join(root, d)
            shutil.rmtree(path)
            count += 1
print(f"Cleaned {count} __pycache__ directories")
