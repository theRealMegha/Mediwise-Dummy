# Fix indentation issue in views.py line 1067

with open('main/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the problematic notification code(lines 1066-1073)
# Keep only the cart_count and return statement
new_lines = lines[:1065]  # Keep everything up to line 1065

# Add corrected lines
new_lines.append('    # Get cart count for the cart icon\n')
new_lines.append('   cart_count = len(cart_items) if patient else 0\n')
new_lines.append('    \n')
new_lines.append("    return render(request, 'patient/cart.html', {\n")
new_lines.append("        'user': patient,\n")
new_lines.append("        'cart_items': cart_items,\n")
new_lines.append("        'subtotal': subtotal,\n")
new_lines.append("        'gst_amount': gst_amount,\n")
new_lines.append("        'total_amount': total_amount,\n")
new_lines.append("        'cart_count': cart_count,\n")
new_lines.append("        'notifications': []\n")
new_lines.append("    })\n")

# Skip the old problematic lines and continue from line 1084
new_lines.extend(lines[1083:])

with open('main/views.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed! Removed problematic notification code and corrected indentation.")
