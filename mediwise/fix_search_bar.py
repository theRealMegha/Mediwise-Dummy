# Fix the search bar issue in pharmacy_medicines view

with open('main/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the section
new_lines = []
skip_until_line = -1

for i, line in enumerate(lines, 1):
    if i == 838 and '    else:' in line:
        # Skip the old else block
        new_lines.append('    \n')
        new_lines.append('    # Support general search in both modes (prescription and regular)\n')
        new_lines.append("    search_term = request.GET.get('search', '')\n")
        new_lines.append('    if search_term and not show_prescription_meds:\n')
        # Next 5 lines will be skipped
        skip_until_line = i + 6
    elif i <= skip_until_line:
        continue
    else:
        new_lines.append(line)

with open('main/views.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Fixed search bar functionality!')
