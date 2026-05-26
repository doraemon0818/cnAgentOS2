import os, glob

base = r'd:\Projects\shixun\day4\aiAgentOS\app'

py_files = glob.glob(os.path.join(base, '**', '*.py'), recursive=True)

total = 0
for py_file in py_files:
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()
    old = "datetime('now')"
    if old in content:
        content = content.replace(old, "datetime('now','localtime')")
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(content)
        cnt = content.count("datetime('now','localtime')")
        print(f"Fixed {py_file}: {cnt} occurrences")
        total += cnt

print(f"\nTotal replacements: {total}")