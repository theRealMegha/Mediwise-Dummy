# Final fix for views.py indentation

with open('main/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the problematic lines 1063-1066 and keep only clean version
new_lines = lines[:1062]  # Keep up to line 1062

# Add clean corrected version
new_lines.append('    # Get cart count for the cart icon\n')
new_lines.append('  cart_count = len(cart_items) if patient else 0\n')
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

# Continue from line 1077
new_lines.extend(lines[1076:])

with open('main/views.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Final fix applied successfully!")
