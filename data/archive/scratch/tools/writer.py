import sys
target = sys.argv[1]
with open(target, 'w', encoding='utf-8') as out:
    out.write(sys.stdin.read())
