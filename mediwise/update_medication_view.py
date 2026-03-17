# Script to change medication_management view to show pharmacies instead of medications
with open('main/views.py', 'r') as f:
    content = f.read()

# Find and replace the function
old_function = '''def medication_management(request):
    if not request.session.get('admin_id'): return redirect('login')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            medicine_id = request.POST.get('medicine_id')
            Medicine.objects.filter(id=medicine_id).delete()
            messages.success(request, "Medication removed successfully.")
            return redirect('medication_management')

    from django.db.models import Sum, F
    # Fetch all medicines and annotate with purchase details using the correct related_name
    medicines = Medicine.objects.all().annotate(
        total_sold=Sum('purchase_items__quantity'),
        total_revenue=Sum(F('purchase_items__quantity') * F('purchase_items__price_at_order'))
    ).order_by('-total_sold')
    
    return render(request, 'admin/medications.html', {'medicines': medicines})'''

new_function = '''def medication_management(request):
    """View for managing and viewing all registered pharmacies"""
    if not request.session.get('admin_id'): return redirect('login')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            pharmacist_id = request.POST.get('pharmacist_id')
            Pharmacist.objects.filter(id=pharmacist_id).delete()
            messages.success(request, "Pharmacy removed successfully.")
            return redirect('medication_management')

    # Fetch all registered pharmacies
    pharmacies = Pharmacist.objects.all().order_by('pharmacy_name')
    
    return render(request, 'admin/medications.html', {'pharmacies': pharmacies})'''

content = content.replace(old_function, new_function)

with open('main/views.py', 'w') as f:
    f.write(content)

print("Successfully updated medication_management view to show pharmacies!")
