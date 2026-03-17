"""
Script to fix the add_lab_test_direct view to handle AJAX requests properly
"""

import re

# Read the file
with open('e:\\Mediwise-Dummy\\mediwise\\main\\views.py', 'r', encoding='utf-8') as f:
   content = f.read()

# Find and replace the specific section
old_code = '''       if lab_tests_added > 0:
           messages.success(request, f"Direct lab test prescription with {lab_tests_added} lab test(s) added successfully!")
            return redirect('doctor_patients')
        else:
           messages.error(request, "No lab tests were added. Please add at least one test.")
            prescription.delete()  # Clean up empty prescription'''

new_code = '''       if lab_tests_added > 0:
           messages.success(request, f"Direct lab test prescription with {lab_tests_added} lab test(s) added successfully!")
            
            # Check if this is an AJAX request
           if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
               from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'message': f'{lab_tests_added} lab test(s) added successfully!'
                })
            
            return redirect('doctor_patients')
        else:
           messages.error(request, "No lab tests were added. Please add at least one test.")
            prescription.delete()  # Clean up empty prescription
            
            # Check if this is an AJAX request
           if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
               from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': 'No lab tests were added.'
                }, status=400)'''

# Perform the replacement
if old_code in content:
   content = content.replace(old_code, new_code)
    
    # Write back
    with open('e:\\Mediwise-Dummy\\mediwise\\main\\views.py', 'w', encoding='utf-8') as f:
       f.write(content)
    
    print("✓ Successfully updated views.py to handle AJAX requests!")
else:
    print("✗ Could not find the target code section. Manual update required.")
    print("\nLooking for:")
    print(repr(old_code[:100]))
