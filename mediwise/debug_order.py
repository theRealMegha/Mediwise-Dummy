from main.models import Order, OrderItem, Medicine, Pharmacist

# Check if order #17 exists
print("=== Order #17 Status ===")
order_exists = Order.objects.filter(id=17).exists()
print(f"Order #17 exists: {order_exists}")

if order_exists:
    order = Order.objects.get(id=17)
    print(f"Order ID: {order.id}")
    print(f"Patient: {order.patient.first_name} {order.patient.last_name}")
    print(f"Order status: {order.status}")
    print(f"Created at: {order.created_at}")
    
    # Check order items
    order_items = order.items.all()
    print(f"\n=== Order Items ({len(order_items)} items) ===")
    for item in order_items:
        print(f"- {item.medicine.brand_name} (Pharmacist: {item.medicine.pharmacist.first_name if item.medicine.pharmacist else 'None'})")
    
    # Check if current pharmacist has medicines in this order
    print(f"\n=== Pharmacist Session Check ===")
    # You'll need to provide the pharmacist_id from session
    # For now, let's check all pharmacists
    pharmacists = Pharmacist.objects.all()
    print(f"Total pharmacists: {len(pharmacists)}")
    
    for pharmacist in pharmacists:
        pharmacist_medicines = Medicine.objects.filter(pharmacist=pharmacist)
        order_items_for_pharmacist = OrderItem.objects.filter(order=order, medicine__in=pharmacist_medicines)
        print(f"Pharmacist {pharmacist.first_name} {pharmacist.last_name}: {order_items_for_pharmacist.count()} items in order")
else:
    print("Order #17 does not exist in the database")