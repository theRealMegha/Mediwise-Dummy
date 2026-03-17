"""
Test script to verify that prescription medicines are searched across ALL pharmacies
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediwise.settings')
django.setup()

from main.models import Medicine, Pharmacist

def test_medicine_search():
    print("=" * 80)
    print("Testing Medicine Search Across All Pharmacies")
    print("=" * 80)
    
    # Get all medicines
    all_medicines = Medicine.objects.all()
    print(f"\nTotal medicines in database: {all_medicines.count()}")
    
    # Group by generic name
    medicine_names = set()
    for med in all_medicines:
        medicine_names.add(med.generic_name.lower().strip())
    
    print(f"Unique medicine names: {len(medicine_names)}")
    
    # Find medicines available in multiple pharmacies
    from collections import defaultdict
    medicine_pharmacies = defaultdict(list)
    
    for med in all_medicines:
        key = med.generic_name.lower().strip()
        medicine_pharmacies[key].append({
            'pharmacy': med.pharmacist.pharmacy_name,
            'stock': med.quantity,
            'price': med.price
        })
    
    # Show medicines available in multiple pharmacies
    multi_pharmacy_medicines = {
        name: pharmacies 
        for name, pharmacies in medicine_pharmacies.items() 
        if len(pharmacies) > 1
    }
    
    print(f"\nMedicines available in MULTIPLE pharmacies: {len(multi_pharmacy_medicines)}")
    print("\n" + "-" * 80)
    
    for name, pharmacies in list(multi_pharmacy_medicines.items())[:5]:  # Show first 5
        print(f"\n{name.upper()}:")
        for ph in pharmacies:
            print(f"  - {ph['pharmacy']}: Stock={ph['stock']}, Price=₹{ph['price']}")
    
    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)
    
    return len(multi_pharmacy_medicines) > 0

if __name__ == '__main__':
    has_multi_pharmacy = test_medicine_search()
    if has_multi_pharmacy:
        print("\n✓ SUCCESS: Found medicines available in multiple pharmacies!")
        print("The system should now show ALL pharmacies when searching prescriptions.")
    else:
        print("\n⚠ WARNING: No medicines found in multiple pharmacies.")
        print("Add the same medicine to different pharmacies to test the feature.")
