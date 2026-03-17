# Read the file
with open(r'e:\Mediwise-Dummy\mediwise\main\views.py', 'r', encoding='utf-8') as f:
  content = f.read()

# Add AJAX handling for ValueError exception
old_value_error = '''       except ValueError as ve:
           messages.error(request, str(ve))'''

new_value_error = '''       except ValueError as ve:
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
  print("Added AJAX handling for ValueError")
else:
  print("Could not find ValueError case - checking content around line 4388")
   # Try to find it with different whitespace
   import re
  pattern = r'except ValueError as ve:\s+messages\.error\(request, str\(ve\)\)'
  match = re.search(pattern, content)
  if match:
      print(f"Found ValueError at position {match.start()}")
      print(f"Context: {content[match.start()-50:match.end()+50]}")

# Add AJAX handling for general Exception
old_exception = '''       except Exception as e:
           messages.error(request, f"System Error: {str(e)}")'''

new_exception = '''       except Exception as e:
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
  print("Added AJAX handling for general exceptions")
else:
  print("Could not find general exception case")

# Write back
with open(r'e:\Mediwise-Dummy\mediwise\main\views.py', 'w', encoding='utf-8') as f:
  f.write(content)

print("\nDone!")
