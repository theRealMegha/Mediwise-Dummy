"""
Script to add AJAX response handling to add_lab_test_direct view
"""

# Read the file
with open(r'e:\Mediwise-Dummy\mediwise\main\views.py', 'r', encoding='utf-8') as f:
   content = f.read()

# Find the success redirect and add AJAX handling before it
old_success = '''messages.success(request, f"Successfully added {lab_tests_added} lab test(s).")
                    return redirect('doctor_patients')'''

new_success= '''messages.success(request, f"Successfully added {lab_tests_added} lab test(s).")
                    
                    # Check if this is an AJAX request
                   if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                       from django.http import JsonResponse
                        return JsonResponse({
                            'success': True,
                            'message': f'Successfully added {lab_tests_added} lab test(s).'
                        })
                    
                    return redirect('doctor_patients')'''

if old_success in content:
   content = content.replace(old_success, new_success)
    print("✓ Added AJAX handling for success case")
else:
    print("✗ Could not find success case")

# Add AJAX handling for ValueError exception
old_value_error = '''except ValueError as ve:
           messages.error(request, str(ve))'''

new_value_error = '''except ValueError as ve:
           messages.error(request, str(ve))
            # Check if this is an AJAX request
           if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
               from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': str(ve)
                }, status=400)'''

if old_value_error in content:
   content = content.replace(old_value_error, new_value_error)
    print("✓ Added AJAX handling for ValueError")
else:
    print("✗ Could not find ValueError case")

# Add AJAX handling for general Exception
old_exception = '''except Exception as e:
           messages.error(request, f"System Error: {str(e)}")'''

new_exception = '''except Exception as e:
           messages.error(request, f"System Error: {str(e)}")
            # Check if this is an AJAX request
           if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
               from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': f"System Error: {str(e)}"
                }, status=500)'''

if old_exception in content:
   content = content.replace(old_exception, new_exception)
    print("✓ Added AJAX handling for general exceptions")
else:
    print("✗ Could not find general exception case")

# Write back
with open(r'e:\Mediwise-Dummy\mediwise\main\views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Successfully updated views.py with AJAX response handling!")
print("\nNow restart your Django server to test the changes.")
