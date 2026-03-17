# Remove duplicate line in views.py

with open('main/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove line 1063 (duplicate comment)
del lines[1062]  # Line 1063 is at index 1062

with open('main/views.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Removed duplicate comment line!")
