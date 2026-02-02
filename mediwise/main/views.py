from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import MediAdmin, Patient, Users, Doctor, Pharmacist, Medicine, Cart,Transaction,OrderItem,Order, Appointment, Prescription, PrescriptionMedicine, Notification, Review, PrescriptionUpload
from .forms import PatientRegistrationForm, PharmacistRegistrationForm, PatientProfileUpdateForm, DoctorRegistrationForm, PharmacistProfileUpdateForm, MedicineForm
from django.contrib import messages
from django.db.models import Q



# Create your views here.

def index(request):
    return render(request, 'index.html')

def getUser(email, password): # Import here to avoid circular import
    mapping = {
        'admin': MediAdmin,
        'patient': Patient,
        'pharmacist': Pharmacist,
        'doctor': Doctor
    }

    for role, model in mapping.items():
        user = model.objects.filter(email=email, password=password).first()
        if user:
            return role, user # Return the object too so you can use it
    return None, None

def login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        role, user_obj = getUser(email, password)
        
        if role == 'admin':
            request.session['admin_id'] = user_obj.id
            return redirect('admin_dashboard')
        elif role == 'patient':
            request.session['patient_id'] = user_obj.id
            return redirect('patient_dashboard')
        elif role == 'pharmacist':
            request.session['pharmacist_id'] = user_obj.id
            return redirect('pharmacist_dashboard')
        elif role == 'doctor':
            request.session['doctor_id'] = user_obj.id
            return redirect('doctor_dashboard')
        
        return render(request, 'login.html', {'error': 'Invalid credentials'})
        
    return render(request, 'login.html')

def logout(request):
    request.session.flush()
    return redirect('index')

def admin_dashboard(request):
    # Check if admin is logged in
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login')
    
    try:
        admin = MediAdmin.objects.get(id=admin_id)
    except MediAdmin.DoesNotExist:
        return redirect('login')
    
    # Real metrics for the dashboard
    total_patients = Patient.objects.count()
    total_doctors = Doctor.objects.count()
    total_meds = Medicine.objects.count()
    
    # Placeholder for recent activity (using patients for now until we have orders)
    recent_patients = Patient.objects.all().order_by('-id')[:5]
    
    # Top Performing Doctors based on ratings
    from django.db.models import Avg, Count
    from .models import Review
    
    # Get top doctors by average rating and review count
    top_doctors = []
    doctor_reviews = Review.objects.filter(
        review_type='doctor'
    ).select_related('doctor').values('doctor').annotate(
        avg_rating=Avg('rating'),
        review_count=Count('id')
    ).order_by('-avg_rating', '-review_count')[:5]
    
    for dr in doctor_reviews:
        doctor = Doctor.objects.get(id=dr['doctor'])
        top_doctors.append({
            'doctor': doctor,
            'avg_rating': dr['avg_rating'],
            'review_count': dr['review_count']
        })
    
    # Get top pharmacists by average rating and review count
    top_pharmacists = []
    
    # First get all orders that have reviews and are linked to pharmacists
    pharmacist_reviews = Review.objects.filter(
        review_type='order'
    ).select_related('order__items__medicine__pharmacist').values(
        'order__items__medicine__pharmacist'
    ).annotate(
        avg_rating=Avg('rating'),
        review_count=Count('id')
    ).exclude(order__items__medicine__pharmacist__isnull=True).order_by('-avg_rating', '-review_count')[:5]
    
    for ph in pharmacist_reviews:
        if ph['order__items__medicine__pharmacist']:  # Make sure it's not null
            try:
                pharmacist = Pharmacist.objects.get(id=ph['order__items__medicine__pharmacist'])
                top_pharmacists.append({
                    'pharmacist': pharmacist,
                    'avg_rating': ph['avg_rating'],
                    'review_count': ph['review_count']
                })
            except Pharmacist.DoesNotExist:
                continue  # Skip if pharmacist doesn't exist
    
    # Calculate revenue from appointments and medicine bookings
    from django.db.models import Sum, F, DecimalField
    from decimal import Decimal
    
    # Calculate total revenue from transactions
    total_revenue = Decimal('0.00')
    appointment_revenue = Decimal('0.00')
    medicine_revenue = Decimal('0.00')
    
    # Get all transactions
    from .models import Transaction, Order
    transactions = Transaction.objects.select_related('order').all()
    
    for transaction in transactions:
        total_revenue += transaction.amount
        
        # Check if transaction is related to an order (medicine booking)
        if hasattr(transaction, 'order') and transaction.order:
            # This is a medicine booking revenue
            medicine_revenue += transaction.amount
        else:
            # Otherwise consider it as appointment revenue
            appointment_revenue += transaction.amount
    
    # Calculate percentages
    if total_revenue > 0:
        appointment_percentage = float(appointment_revenue / total_revenue * 100)
        medicine_percentage = float(medicine_revenue / total_revenue * 100)
    else:
        appointment_percentage = 0
        medicine_percentage = 0
    
    # Calculate refill analytics
    from .models import OrderItem
    
    # Get all orders that have course duration set (indicating long-term medication)
    total_long_term_orders = OrderItem.objects.filter(course_duration__isnull=False).count()
    
    # Get orders that have been reordered (refilled)
    # This is a simplified approach - in a real scenario, you'd need to check if the same medicine was ordered again
    refilled_orders = OrderItem.objects.filter(course_duration__isnull=False, reminder_sent_at__isnull=False).count()
    
    if total_long_term_orders > 0:
        refill_percentage = (refilled_orders / total_long_term_orders) * 100
    else:
        refill_percentage = 0
    
    # Create recent activity feed
    recent_activities = []
    
    # Add recent patients
    from django.utils import timezone
    recent_patients_db = Patient.objects.order_by('-id')[:2]
    for patient in recent_patients_db:
        recent_activities.append({
            'message': f'New patient registered: {patient.first_name} {patient.last_name}',
            'timestamp': patient.id  # Using ID as proxy for timestamp
        })
    
    # Add recent appointments
    from .models import Appointment
    recent_appts = Appointment.objects.select_related('patient', 'doctor').order_by('-id')[:2]
    for appt in recent_appts:
        recent_activities.append({
            'message': f'Appointment scheduled for {appt.patient.first_name} {appt.patient.last_name} with Dr. {appt.doctor.first_name}',
            'timestamp': appt.id  # Using ID as proxy for timestamp
        })
    
    # Add recent prescriptions
    recent_prescriptions = Prescription.objects.select_related('patient', 'doctor').order_by('-id')[:1]
    for presc in recent_prescriptions:
        recent_activities.append({
            'message': f'New prescription generated by Dr. {presc.doctor.first_name} for {presc.patient.first_name} {presc.patient.last_name}',
            'timestamp': presc.id  # Using ID as proxy for timestamp
        })
    
    # Add recent orders
    from .models import Order
    recent_orders = Order.objects.select_related('patient').order_by('-id')[:2]
    for order in recent_orders:
        recent_activities.append({
            'message': f'Medicine order #{order.id} placed by {order.patient.first_name} {order.patient.last_name}',
            'timestamp': order.id  # Using ID as proxy for timestamp
        })
    
    # Sort activities by ID (which approximates chronological order, higher ID = more recent)
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:5]  # Take only the 5 most recent
    
    context = {
        'admin': admin,
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_meds': total_meds,
        'recent_patients': recent_patients,
        'top_doctors': top_doctors,
        'top_pharmacists': top_pharmacists,
        'appointment_revenue': appointment_revenue,
        'medicine_revenue': medicine_revenue,
        'total_revenue': total_revenue,
        'appointment_percentage': appointment_percentage,
        'medicine_percentage': medicine_percentage,
        'refill_percentage': refill_percentage,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'admin/dashboard.html', context)

def patient_dashboard(request):
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    
    user = Patient.objects.filter(id=user_id).first()
    
    # Define which fields are required for a "complete" profile
    # Add or remove fields based on your Patient model
    required_fields = [user.phone_number, user.address, user.date_of_birth, user.blood_group, user.height, user.weight]
    profile_incomplete = any(field in [None, '', 'None'] for field in required_fields)

    # Fetch all pharmacists for the pharmacy view
    pharmacists = Pharmacist.objects.all()
    
    # Get patient's upcoming appointments
    from django.utils import timezone
    appointments = Appointment.objects.filter(
        patient=user,
        appointment_date__gte=timezone.now().date(),
        status__in=['scheduled']
    ).prefetch_related('reviews').order_by('appointment_date', 'appointment_time')
    
    # Get patient's active prescriptions from the Prescription model
    from datetime import timedelta
    from django.db.models import F, ExpressionWrapper, DurationField
    from django.db.models.functions import Cast
        
    # Get all prescriptions for this patient with their medicines
    prescriptions = Prescription.objects.filter(patient=user).select_related('doctor', 'appointment').prefetch_related('medicines').order_by('-created_at')
            
    # Process prescriptions to determine if they're still active
    active_prescriptions = []
    for prescription in prescriptions:
        # Get all medicines for this prescription
        medicines = prescription.medicines.all()
            
        # Calculate remaining days based on course duration (using first medicine as reference)
        if medicines.exists():
            first_medicine = medicines.first()
            try:
                # Extract days from course duration (format: 'X days' or just number)
                course_str = first_medicine.duration_course.lower()
                if 'day' in course_str:
                    # Extract number from string like '7 days', '14 days', etc.
                    import re
                    days_match = re.search(r'(\d+)', course_str)
                    if days_match:
                        total_days = int(days_match.group(1))
                        days_since_prescription = (timezone.now().date() - prescription.created_at.date()).days
                        remaining_days = max(0, total_days - days_since_prescription)
                                
                        # Only add to active prescriptions if still valid (not expired)
                        if remaining_days > 0:
                            # Add each medicine as a separate entry
                            for medicine in medicines:
                                active_prescriptions.append({
                                    'prescription': prescription,
                                    'drug_name': medicine.drug_name_generic,
                                    'strength': medicine.strength,
                                    'duration': medicine.duration_course,
                                    'doctor': prescription.doctor,
                                    'remaining_days': remaining_days,
                                    'prescribed_date': prescription.created_at.date(),
                                    'instructions': medicine.instructions
                                })
                    else:
                        # If no days found in duration, add as N/A but still include in active list
                        for medicine in medicines:
                            active_prescriptions.append({
                                'prescription': prescription,
                                'drug_name': medicine.drug_name_generic,
                                'strength': medicine.strength,
                                'duration': medicine.duration_course,
                                'doctor': prescription.doctor,
                                'remaining_days': 'N/A',
                                'prescribed_date': prescription.created_at.date(),
                                'instructions': medicine.instructions
                            })
                else:
                    # If no 'day' in duration, add as N/A but still include in active list
                    for medicine in medicines:
                        active_prescriptions.append({
                            'prescription': prescription,
                            'drug_name': medicine.drug_name_generic,
                            'strength': medicine.strength,
                            'duration': medicine.duration_course,
                            'doctor': prescription.doctor,
                            'remaining_days': 'N/A',
                            'prescribed_date': prescription.created_at.date(),
                            'instructions': medicine.instructions
                        })
            except:
                # If parsing fails, add as N/A but still include in active list
                for medicine in medicines:
                    active_prescriptions.append({
                        'prescription': prescription,
                        'drug_name': medicine.drug_name_generic,
                        'strength': medicine.strength,
                        'duration': medicine.duration_course,
                        'doctor': prescription.doctor,
                        'remaining_days': 'N/A',
                        'prescribed_date': prescription.created_at.date(),
                        'instructions': medicine.instructions
                    })
        else:
            # Handle prescriptions with no medicines (fallback)
            try:
                # This is a fallback for old prescriptions that might not have medicine entries
                course_str = getattr(prescription, 'duration_course', '30 days').lower()
                if 'day' in course_str:
                    import re
                    days_match = re.search(r'(\d+)', course_str)
                    if days_match:
                        total_days = int(days_match.group(1))
                        days_since_prescription = (timezone.now().date() - prescription.created_at.date()).days
                        remaining_days = max(0, total_days - days_since_prescription)
                        if remaining_days > 0:
                            active_prescriptions.append({
                                'prescription': prescription,
                                'drug_name': 'Multiple Medicines',
                                'strength': 'See details',
                                'duration': prescription.duration_course if hasattr(prescription, 'duration_course') else 'N/A',
                                'doctor': prescription.doctor,
                                'remaining_days': remaining_days,
                                'prescribed_date': prescription.created_at.date(),
                                'instructions': 'See prescription details'
                            })
            except:
                pass
        
    # Limit to the most recent active prescriptions
    active_prescriptions = active_prescriptions[:2]
    
    # Mark all unread notifications as read and update their read_at timestamp
    from .models import Notification
    from django.utils import timezone
    from datetime import timedelta
    
    unread_notifications = Notification.objects.filter(patient=user, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=user
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=user).count() if user else 0
    
    context = {
        'user': user,
        'profile_incomplete': profile_incomplete,
        'pharmacists': pharmacists,
        'appointments': appointments,
        'active_prescriptions': active_prescriptions,
        'notifications': notifications,
        'cart_count': cart_count,
    }
    return render(request, 'patient/dashboard.html', context)

def registered_pharmacies(request):
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    
    user = Patient.objects.filter(id=user_id).first()
    
    # Handle prescription_id parameter to redirect to pharmacy with filtered medicines
    prescription_id = request.GET.get('prescription_id')
    if prescription_id:
        from .models import Prescription
        try:
            prescription = Prescription.objects.get(id=prescription_id, patient=user)
            # Get the first pharmacy to redirect to with prescription medicines filter
            first_pharmacist = Pharmacist.objects.first()
            if first_pharmacist:
                # Redirect to pharmacy medicines page with query parameters to show specific prescription medicines
                from django.urls import reverse
                redirect_url = f"{reverse('pharmacy_medicines', kwargs={'pk': first_pharmacist.id})}?show_prescription_meds=true&prescription_id={prescription_id}"
                return redirect(redirect_url)
        except Prescription.DoesNotExist:
            messages.error(request, "Prescription not found.")
    
    pharmacists = Pharmacist.objects.all()
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=user).count() if user else 0
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=user, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=user
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    return render(request, 'patient/pharmacies.html', {
        'user': user,
        'pharmacists': pharmacists,
        'notifications': notifications,
        'cart_count': cart_count
    })

def pharmacy_medicines(request, pk):
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    
    user = Patient.objects.filter(id=user_id).first()
    pharmacist = Pharmacist.objects.filter(id=pk).first()
    if not pharmacist:
        messages.error(request, "Pharmacy not found.")
        return redirect('registered_pharmacies')
    
    # Get medicines for this pharmacist
    medicines = Medicine.objects.filter(pharmacist=pharmacist)
    
    # Check if user wants to see medicines from their prescriptions
    show_prescription_meds = request.GET.get('show_prescription_meds', False)
    
    if show_prescription_meds:
        # Get medicines from patient's prescriptions
        from .models import Prescription, PrescriptionMedicine
        
        # Check if a specific prescription ID was passed
        specific_prescription_id = request.GET.get('prescription_id')
        
        if specific_prescription_id:
            # Get medicines from a specific prescription
            try:
                specific_prescription = Prescription.objects.get(id=specific_prescription_id, patient=user)
                prescription_medicines = PrescriptionMedicine.objects.filter(prescription=specific_prescription)
            except Prescription.DoesNotExist:
                # If specific prescription not found, return empty queryset
                medicines = Medicine.objects.none()
                prescription_med_names = set()
        else:
            # Get all prescription medicines for this patient
            prescription_medicines = PrescriptionMedicine.objects.filter(
                prescription__patient=user
            ).select_related('prescription')
        
        # Extract medicine names from prescriptions (both generic and brand names)
        prescription_med_names = set()
        prescription_medicine_details = []  # Store detailed info about prescription medicines
        for prescription_medicine in prescription_medicines:
            if prescription_medicine.drug_name_generic:
                prescription_med_names.add(prescription_medicine.drug_name_generic.lower())
                prescription_medicine_details.append({
                    'name': prescription_medicine.drug_name_generic,
                    'type': 'generic'
                })
            if prescription_medicine.drug_name_brand:
                prescription_med_names.add(prescription_medicine.drug_name_brand.lower())
                prescription_medicine_details.append({
                    'name': prescription_medicine.drug_name_brand,
                    'type': 'brand'
                })
        
        # Filter medicines that match prescription medicines using case-insensitive partial matching
        if prescription_med_names:
            from django.db.models import Q
            q_objects = Q()
            for med_name in prescription_med_names:
                q_objects |= Q(generic_name__icontains=med_name)
                q_objects |= Q(brand_name__icontains=med_name)
            medicines = medicines.filter(q_objects).distinct()
            
            # Get the names of available medicines in this pharmacist's inventory
            available_medicine_names = set()
            for med in medicines:
                available_medicine_names.add(med.generic_name.lower())
                available_medicine_names.add(med.brand_name.lower())
            
            # Identify which prescription medicines are not available
            unavailable_medicines = []
            for med_detail in prescription_medicine_details:
                med_name_lower = med_detail['name'].lower()
                # Check if this medicine name matches any available medicine
                found = False
                for avail_name in available_medicine_names:
                    if avail_name and med_name_lower in avail_name or avail_name in med_name_lower:
                        found = True
                        break
                if not found and med_name_lower.strip():
                    unavailable_medicines.append(med_detail['name'])
            
            # Pass unavailable medicines to the template
            request.unavailable_prescription_medicines = unavailable_medicines
        else:
            # If no prescription medicines, return empty queryset
            medicines = Medicine.objects.none()
            request.unavailable_prescription_medicines = []
    else:
        # If there's a search term, filter medicines
        search_term = request.GET.get('search', '')
        if search_term:
            medicines = medicines.filter(
                Q(generic_name__icontains=search_term) |
                Q(brand_name__icontains=search_term) |
                Q(strength__icontains=search_term)
            )
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=user).count() if user else 0
    
    # Get unavailable medicines if in prescription mode
    unavailable_prescription_medicines = getattr(request, 'unavailable_prescription_medicines', [])
    
    return render(request, 'patient/pharmacy_medicines.html', {
        'user': user,
        'pharmacist': pharmacist,
        'medicines': medicines,
        'cart_count': cart_count,
        'search_term': request.GET.get('search', ''),
        'show_prescription_meds': bool(show_prescription_meds),
        'unavailable_prescription_medicines': unavailable_prescription_medicines
    })

def add_to_cart(request, medicine_id):
    if request.method != 'POST' and request.GET.get('course_duration'):
        # Allow GET requests when course_duration is provided in URL for prescription medicines
        pass  # Continue with the logic
    elif request.method != 'POST':
        return redirect('pharmacy_medicines', pk=1)  # Fallback redirect
    
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=patient_id)
    medicine = Medicine.objects.get(id=medicine_id)
    
    # Handle course duration - prioritize any duration passed in request
    course_duration = request.POST.get('course_duration', '')
    # Also check for course duration in GET parameters (for direct links from prescriptions)
    if not course_duration:
        course_duration = request.GET.get('course_duration', '')
    
    # If no course duration was provided in the request, try to get it from patient's prescriptions
    if not course_duration:
        from .models import PrescriptionUpload
        # Look for uploaded prescriptions that contain this medicine
        # Since JSONField lookup is tricky, we'll filter in Python
        all_prescriptions = PrescriptionUpload.objects.filter(patient=patient)
        uploaded_prescriptions = []
        for prescription in all_prescriptions:
            for med in prescription.extracted_medicines:
                if med.get('name', '').lower().strip() == medicine.generic_name.lower().strip():
                    uploaded_prescriptions.append(prescription)
                    break
        
        # Try to find the course duration from any of these prescriptions using flexible matching
        for prescription in uploaded_prescriptions:
            for med in prescription.extracted_medicines:
                # Use more flexible matching to find the medicine in prescriptions
                med_name = med.get('name', '').lower().strip()
                generic_name = medicine.generic_name.lower().strip()
                
                # Check if the medicine names match (case-insensitive, partial match)
                if (med_name == generic_name or 
                    generic_name in med_name or 
                    med_name in generic_name):
                    
                    if med.get('duration'):
                        course_duration = med['duration']
                        break
            if course_duration:
                break
    
    # Try to extract quantity from prescription as well
    prescribed_quantity = 1  # Default quantity
    # Look for prescribed quantity in patient's prescriptions
    all_prescriptions = PrescriptionUpload.objects.filter(patient=patient)
    for prescription in all_prescriptions:
        for med in prescription.extracted_medicines:
            # Use more flexible matching to find the medicine in prescriptions
            med_name = med.get('name', '').lower().strip()
            generic_name = medicine.generic_name.lower().strip()
            
            # Check if the medicine names match (case-insensitive, partial match)
            if (med_name == generic_name or 
                generic_name in med_name or 
                med_name in generic_name):
                
                # Extract quantity from prescription if available
                if med.get('quantity'):
                    # Try to parse the quantity from the prescription string
                    import re
                    # Look for numeric values in the quantity string
                    quantity_match = re.search(r'(\d+)', str(med['quantity']))
                    if quantity_match:
                        prescribed_quantity = int(quantity_match.group(1))
                    else:
                        # If no number found, default to 1
                        prescribed_quantity = 1
                break
        if prescribed_quantity != 1:
            break
    
    # Check if medicine is being added from a prescription context
    # This can be from prescription upload page, or from pharmacy medicines page when showing prescription meds
    is_from_prescription = (
        bool(course_duration) or  # If course duration is provided from prescription
        request.GET.get('from_prescription') == 'true' or  # Explicit flag from prescription context
        'show_prescription_meds=true' in request.META.get('HTTP_REFERER', '') or  # From prescription meds view
        'prescription_id' in request.META.get('HTTP_REFERER', '')  # From specific prescription view
    )
    
    # Check if medicine is Rx (requires prescription)
    if medicine.medicine_type == 'Rx':
        # Add medicine to cart but mark as requiring prescription
        cart_item, created = Cart.objects.get_or_create(patient=patient, medicine=medicine)
        cart_item.requires_prescription = True
        
        # If medicine is being added from a prescription context, mark it as such
        if is_from_prescription:
            cart_item.added_from_prescription = True
        
        # Set quantity from prescription if available, otherwise default to 1
        cart_item.quantity = prescribed_quantity
        
        # Set course duration if provided
        if course_duration:
            cart_item.course_duration = course_duration
        
        cart_item.save()
        
        # Show appropriate message based on context
        if is_from_prescription:
            messages.success(request, f"{medicine.brand_name} added to cart from prescription.")
        else:
            messages.warning(request, f"{medicine.brand_name} is a prescription-only medicine. You will need to upload a prescription before checkout.")
        return redirect('view_cart')
    
    # For OTC medicines, proceed normally
    if medicine.quantity > 0:
        cart_item, created = Cart.objects.get_or_create(patient=patient, medicine=medicine)
        
        # Set quantity from prescription if available and we're not incrementing an existing item
        if not created:
            # If item already exists, increment by 1 (normal behavior)
            cart_item.quantity += 1
        else:
            # If new item, try to set quantity from prescription
            cart_item.quantity = prescribed_quantity
        
        # Set course duration if provided
        if course_duration:
            cart_item.course_duration = course_duration
        
        # If medicine is being added from a prescription context, mark it as such
        if is_from_prescription:
            cart_item.added_from_prescription = True
        
        cart_item.save()
        messages.success(request, f"{medicine.brand_name} added to cart.")
        return redirect('view_cart')
    else:
        messages.error(request, "Medicine out of stock.")
        return redirect('pharmacy_medicines', pk=medicine.pharmacist.id)

def view_cart(request):
    from decimal import Decimal
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=patient_id)
    cart_items = Cart.objects.filter(patient=patient)
    
    # Calculate subtotal
    subtotal = 0
    for item in cart_items:
        subtotal += item.medicine.price * item.quantity
    
    # Calculate GST (18%)
    gst_rate = Decimal('0.18')
    gst_amount = round(subtotal * gst_rate, 2)
    total_amount = subtotal + gst_amount
    
    # Get cart count for the cart icon
    cart_count = cart_items.count() if patient else 0
    
    return render(request, 'patient/cart.html', {
        'user': patient,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'gst_amount': gst_amount,
        'total_amount': total_amount,
        'cart_count': cart_count
    })

def update_cart_quantity(request, item_id, action):
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    cart_item = Cart.objects.filter(id=item_id, patient_id=patient_id).first()
    if not cart_item:
        return redirect('view_cart')
    
    if action == 'increase':
        if cart_item.quantity < cart_item.medicine.quantity:
            cart_item.quantity += 1
            cart_item.save()
        else:
            messages.warning(request, "Cannot exceed available stock.")
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
            messages.info(request, "Item removed from cart.")
            
    return redirect('view_cart')

def update_cart_course_duration(request):
    if request.method != 'POST':
        return redirect('view_cart')
    
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    # Process all course duration fields in the POST data
    for key, value in request.POST.items():
        if key.startswith('course_duration_'):
            # Extract cart item ID from the field name
            try:
                cart_item_id = int(key.replace('course_duration_', ''))
                # Update the corresponding cart item
                cart_item = Cart.objects.filter(id=cart_item_id, patient_id=patient_id).first()
                if cart_item:
                    cart_item.course_duration = value
                    cart_item.save()
            except ValueError:
                # Skip if the ID is not a valid integer
                continue
    
    messages.success(request, "Course durations saved successfully!")
    return redirect('view_cart')

def remove_from_cart(request, item_id):
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    cart_item = Cart.objects.filter(id=item_id, patient_id=patient_id).first()
    if cart_item:
        medicine_name = cart_item.medicine.brand_name
        cart_item.delete()
        messages.info(request, f"{medicine_name} removed from cart.")
            
    return redirect('view_cart')

def checkout(request):
    import uuid
    from decimal import Decimal
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=patient_id)
    cart_items = Cart.objects.filter(patient=patient)
    
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('view_cart')
    
    # Check for Rx medicines that require prescriptions
    rx_items = cart_items.filter(requires_prescription=True)
    if rx_items.exists():
        # Check each Rx medicine individually to see if it's covered by a prescription
        from .models import PrescriptionUpload
        uploaded_prescriptions = PrescriptionUpload.objects.filter(
            patient=patient,
            status__in=['processed', 'partially_available']
        ).order_by('-created_at')  # Most recent first
        
        # Check each Rx item in the cart
        for rx_item in rx_items:
            # If the medicine was added directly from a prescription, skip the prescription check
            if rx_item.added_from_prescription:
                continue
            
            rx_medicine_name = rx_item.medicine.generic_name.lower().strip()
            has_prescription_for_this_medicine = False
            
            # Look through all uploaded prescriptions to find one that contains this specific medicine
            for uploaded_prescription in uploaded_prescriptions:
                extracted_medicines = uploaded_prescription.extracted_medicines
                for med in extracted_medicines:
                    med_name = med.get('name', '').lower().strip()
                    
                    # Use flexible matching to find the medicine in the prescription
                    if (med_name == rx_medicine_name or 
                        rx_medicine_name in med_name or 
                        med_name in rx_medicine_name):
                        has_prescription_for_this_medicine = True
                        break
                
                if has_prescription_for_this_medicine:
                    break
            
            # If this Rx medicine doesn't have a matching prescription, block checkout
            if not has_prescription_for_this_medicine:
                messages.error(request, f"Prescription required for {rx_item.medicine.generic_name}. Please upload a prescription containing this medicine before proceeding to checkout.")
                return redirect('view_cart')
    
    # Calculate total amount and verify stock
    subtotal = 0
    for item in cart_items:
        if item.medicine.quantity < item.quantity:
            messages.error(request, f"Not enough stock for {item.medicine.brand_name}.")
            return redirect('view_cart')
        subtotal += item.medicine.price * item.quantity
    
    # Calculate GST (assuming 18% standard rate for medicines)
    GST_RATE = Decimal('0.18')
    gst_amount = round(subtotal * GST_RATE, 2)
    total_amount = subtotal + gst_amount
    
    # Create Order
    order = Order.objects.create(
        patient=patient,
        total_amount=total_amount,
        gst_amount=gst_amount,
        # Default status is 'pending' as defined in the model
    )
    
    # Create Order Items and Update Stock
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            medicine=item.medicine,
            quantity=item.quantity,
            price_at_order=item.medicine.price,
            course_duration=item.course_duration
        )
        item.medicine.quantity -= item.quantity
        item.medicine.save()
    
    # Create Transaction
    Transaction.objects.create(
        order=order,
        transaction_id=f"MW-{uuid.uuid4().hex[:8].upper()}",
        amount=total_amount
    )
    
    # Clear cart
    cart_items.delete()
    
    messages.success(request, "Payment successful! Your order has been placed.")
    return redirect('patient_dashboard')

def patient_records(request):
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    user = Patient.objects.filter(id=user_id).first()
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=user).count() if user else 0
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=user, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=user
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    return render(request, 'patient/records.html', {
        'user': user, 
        'notifications': notifications,
        'cart_count': cart_count
    })

def patient_orders(request):
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=patient_id)
    orders = Order.objects.filter(patient=patient).prefetch_related('items__medicine__pharmacist', 'transaction', 'reviews').order_by('-created_at')
    
    # Add unique pharmacists for each order
    for order in orders:
        pharmacists_set = set()
        for item in order.items.all():
            if item.medicine.pharmacist:
                pharmacists_set.add(item.medicine.pharmacist)
        order.unique_pharmacists = list(pharmacists_set)
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    return render(request, 'patient/orders.html', {
        'user': patient,
        'orders': orders,
        'notifications': notifications,
        'cart_count': cart_count
    })

def patient_prescriptions(request):
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Get all prescriptions for this patient with their medicines
    prescriptions = Prescription.objects.filter(patient=patient).select_related('doctor', 'appointment').prefetch_related('medicines').order_by('-created_at')
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    context = {
        'user': patient,
        'prescriptions': prescriptions,
        'notifications': notifications,
        'cart_count': cart_count,
    }
    return render(request, 'patient/prescriptions.html', context)


def extract_medicines_from_prescription(prescription_upload):
    """Simulate medicine extraction from prescription (would be OCR in real implementation)"""
    # This is a simulation of what OCR would extract
    # In real implementation, this would use an OCR service like Google Vision API
    
    # Get actual medicines from the database to ensure accurate matching
    from .models import Medicine
    database_medicines = list(Medicine.objects.all().values('generic_name', 'brand_name'))
    
    # Map database medicines to prescription format
    available_medicines = []
    
    # Common medicine templates with realistic dosages
    medicine_templates = {
        'paracetamol': {
            'strength': '500mg',
            'dosage': '1 tablet 3 times daily',
            'duration': '7 days',
            'quantity': '21 tablets'
        },
        'citrizen': {
            'strength': '10mg',
            'dosage': '1 tablet at bedtime',
            'duration': '7 days',
            'quantity': '7 tablets'
        },
        'dolo': {
            'strength': '500mg',
            'dosage': '1 tablet 3 times daily',
            'duration': '7 days',
            'quantity': '21 tablets'
        }
    }
    
    # Match database medicines with templates
    for db_medicine in database_medicines:
        generic_name = db_medicine['generic_name'].lower().strip()
        if generic_name in medicine_templates:
            template = medicine_templates[generic_name]
            available_medicines.append({
                'name': db_medicine['generic_name'],
                'strength': template['strength'],
                'dosage': template['dosage'],
                'duration': template['duration'],
                'quantity': template['quantity']
            })
    
    # If no medicines found in database, return a default medicine
    if not available_medicines:
        available_medicines.append({
            'name': 'Paracetamol',
            'strength': '500mg',
            'dosage': '1 tablet 3 times daily',
            'duration': '7 days',
            'quantity': '21 tablets'
        })
    
    # Select a realistic number of medicines (1-3) to simulate a typical prescription
    import random
    num_medicines = min(random.randint(1, 3), len(available_medicines))  # Most prescriptions contain 1-3 different medicines
    selected_medicines = random.sample(available_medicines, num_medicines)
    
    return selected_medicines

def check_medicine_availability(extracted_medicines, pharmacist=None):
    """Check availability of medicines in specified pharmacy or all pharmacies"""
    from .models import Medicine
    from decimal import Decimal
    
    # If specific pharmacy is specified, check only that pharmacy
    if pharmacist:
        pharmacy_medicines = Medicine.objects.filter(pharmacist=pharmacist)
        pharmacy_list = [pharmacist]
    else:
        # Check all pharmacies
        pharmacy_medicines = Medicine.objects.all()
        pharmacy_list = Pharmacist.objects.all()
    
    # Create medicine dictionary for quick lookup
    medicine_dict = {}
    for med in pharmacy_medicines:
        key = med.generic_name.lower().strip()
        if key not in medicine_dict or med.quantity > medicine_dict[key]['stock']:
            medicine_dict[key] = {
                'medicine': med,
                'stock': med.quantity,
                'price': str(med.price),  # Convert Decimal to string for JSON serialization
                'pharmacy_id': med.pharmacist.id,
                'pharmacy_name': med.pharmacist.pharmacy_name
            }
    
    available_medicines = []
    unavailable_medicines = []
    
    # Check each extracted medicine
    for medicine in extracted_medicines:
        med_name = medicine['name'].lower().strip()
        if med_name in medicine_dict and medicine_dict[med_name]['stock'] > 0:
            available_medicines.append({
                'name': medicine_dict[med_name]['medicine'].generic_name,
                'brand': medicine_dict[med_name]['medicine'].brand_name,
                'strength': medicine_dict[med_name]['medicine'].strength,
                'stock': medicine_dict[med_name]['stock'],
                'price': medicine_dict[med_name]['price'],  # Already string from above
                'pharmacy_id': medicine_dict[med_name]['pharmacy_id'],
                'pharmacy_name': medicine_dict[med_name]['pharmacy_name'],
                'medicine_id': medicine_dict[med_name]['medicine'].id,  # Add medicine ID for cart functionality
                'extracted_info': medicine
            })
        else:
            unavailable_medicines.append({
                'name': medicine['name'],
                'reason': 'Not available in stock',
                'extracted_info': medicine
            })
    
    return available_medicines, unavailable_medicines

def upload_prescription(request, pharmacist_id=None):
    """Allow patients to upload prescriptions either for a specific pharmacy or all pharmacies"""
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Get pharmacist if specified
    pharmacist = None
    if pharmacist_id:
        try:
            pharmacist = Pharmacist.objects.get(id=pharmacist_id)
        except Pharmacist.DoesNotExist:
            messages.error(request, "Pharmacy not found.")
            return redirect('registered_pharmacies')
    
    if request.method == 'POST':
        prescription_image = request.FILES.get('prescription_image')
        notes = request.POST.get('notes', '')
        
        if prescription_image:
            upload = PrescriptionUpload(
                patient=patient,
                pharmacist=pharmacist,
                prescription_image=prescription_image,
                notes=notes
            )
            upload.save()
            
            # Extract medicines from prescription (simulated OCR)
            extracted_medicines = extract_medicines_from_prescription(upload)
            upload.extracted_medicines = extracted_medicines
            
            # Check availability immediately
            available_medicines, unavailable_medicines = check_medicine_availability(extracted_medicines, pharmacist)
            upload.available_medicines = available_medicines
            upload.unavailable_medicines = unavailable_medicines
            
            # Set status based on availability
            if not unavailable_medicines:
                upload.status = 'processed'
            elif available_medicines and unavailable_medicines:
                upload.status = 'partially_available'
            else:
                upload.status = 'not_available'
            
            upload.save()
            
            pharmacy_name = pharmacist.pharmacy_name if pharmacist else "all pharmacies"
            messages.success(request, f"Prescription uploaded successfully for {pharmacy_name}!")
            
            # Redirect to view the uploaded prescription with availability info
            return redirect('view_my_prescriptions')
        else:
            messages.error(request, "Please select a prescription image to upload.")
    
    context = {
        'user': patient,
        'pharmacist': pharmacist,
        'cart_count': Cart.objects.filter(patient=patient).count(),
    }
    
    return render(request, 'patient/upload_prescription.html', context)

def view_my_prescriptions(request):
    """View all prescriptions uploaded by the patient"""
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Get all uploaded prescriptions
    uploaded_prescriptions = PrescriptionUpload.objects.filter(patient=patient).select_related('pharmacist').order_by('-created_at')
    
    # Add medicine availability information
    for upload in uploaded_prescriptions:
        # Get extracted medicines
        upload.extracted_medicines = upload.extracted_medicines or []
        
        # This would be enhanced with medicine matching logic
        upload.availability_info = []
    
    context = {
        'user': patient,
        'uploaded_prescriptions': uploaded_prescriptions,
        'cart_count': Cart.objects.filter(patient=patient).count(),
    }
    
    return render(request, 'patient/my_prescriptions.html', context)

def delete_prescription_upload(request, prescription_id):
    """Allow patients to delete their uploaded prescriptions"""
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
        prescription = PrescriptionUpload.objects.get(id=prescription_id, patient=patient)
    except (Patient.DoesNotExist, PrescriptionUpload.DoesNotExist):
        messages.error(request, "Prescription not found or you don't have permission to delete it.")
        return redirect('view_my_prescriptions')
    
    if request.method == 'POST':
        # Store prescription details for the success message
        pharmacy_name = prescription.pharmacist.pharmacy_name if prescription.pharmacist else "all pharmacies"
        
        # Delete the prescription
        prescription.delete()
        
        messages.success(request, f"Prescription for {pharmacy_name} has been successfully deleted.")
        return redirect('view_my_prescriptions')
    
    context = {
        'user': patient,
        'prescription': prescription,
        'cart_count': Cart.objects.filter(patient=patient).count(),
    }
    
    return render(request, 'patient/delete_prescription.html', context)

def add_all_prescription_medicines_to_cart(request, prescription_id):
    """Add all available medicines from a prescription to the patient's cart"""
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
        prescription = PrescriptionUpload.objects.get(id=prescription_id, patient=patient)
    except (Patient.DoesNotExist, PrescriptionUpload.DoesNotExist):
        messages.error(request, "Prescription not found or you don't have permission to access it.")
        return redirect('view_my_prescriptions')
    
    if request.method == 'POST':
        from .models import Medicine, Cart
        medicines_added = 0
        medicines_skipped = 0
        
        # Get available medicines from the prescription
        available_medicines = prescription.available_medicines or []
        
        for med_data in available_medicines:
            try:
                # Find the actual medicine object
                medicine = Medicine.objects.get(
                    generic_name=med_data['name'],
                    pharmacist_id=med_data['pharmacy_id']
                )
                
                # Check if medicine is already in cart
                existing_cart_item = Cart.objects.filter(
                    patient=patient,
                    medicine=medicine
                ).first()
                
                if existing_cart_item:
                    # Update quantity if already exists
                    existing_cart_item.quantity += 1
                    existing_cart_item.save()
                    medicines_added += 1
                else:
                    # Add new item to cart
                    # Extract duration from prescription data if available
                    duration = "7 days"  # Default duration
                    if med_data.get('duration'):
                        duration = med_data['duration']
                    elif med_data.get('extracted_info') and med_data['extracted_info'].get('duration'):
                        duration = med_data['extracted_info']['duration']
                    
                    # Extract quantity from prescription data if available
                    quantity = 1  # Default quantity
                    if med_data.get('extracted_info') and med_data['extracted_info'].get('quantity'):
                        # Try to parse the quantity from the prescription string
                        import re
                        quantity_match = re.search(r'(\d+)', str(med_data['extracted_info']['quantity']))
                        if quantity_match:
                            quantity = int(quantity_match.group(1))
                        else:
                            # If no number found, default to 1
                            quantity = 1
                    
                    Cart.objects.create(
                        patient=patient,
                        medicine=medicine,
                        quantity=quantity,
                        course_duration=duration,
                        added_from_prescription=True  # Mark as added from prescription
                    )
                    medicines_added += 1
                    
            except Medicine.DoesNotExist:
                medicines_skipped += 1
                continue
        
        # Add success message
        if medicines_added > 0:
            messages.success(request, f"Successfully added {medicines_added} medicine(s) to your cart.")
        if medicines_skipped > 0:
            messages.warning(request, f"{medicines_skipped} medicine(s) could not be added to cart.")
        
        return redirect('view_my_prescriptions')
    
    # If GET request, show confirmation page
    context = {
        'user': patient,
        'prescription': prescription,
        'cart_count': Cart.objects.filter(patient=patient).count(),
    }
    
    return render(request, 'patient/add_prescription_medicines_to_cart.html', context)

def pharmacist_prescription_uploads(request):
    """View prescriptions uploaded for this pharmacist"""
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        return redirect('login')
    
    # Get prescriptions uploaded specifically for this pharmacist
    pharmacy_prescriptions = PrescriptionUpload.objects.filter(
        pharmacist=pharmacist
    ).select_related('patient').order_by('-created_at')
    
    # Get common prescriptions (uploaded for all pharmacies)
    common_prescriptions = PrescriptionUpload.objects.filter(
        pharmacist=None
    ).select_related('patient').order_by('-created_at')
    
    # Combine and sort by date
    all_prescriptions = list(pharmacy_prescriptions) + list(common_prescriptions)
    all_prescriptions.sort(key=lambda x: x.created_at, reverse=True)
    
    # Get all medicines for this pharmacist
    pharmacist_medicines = Medicine.objects.filter(pharmacist=pharmacist)
    medicine_dict = {}
    for med in pharmacist_medicines:
        key = med.generic_name.lower().strip()
        medicine_dict[key] = {
            'medicine': med,
            'stock': med.quantity,
            'price': str(med.price),  # Convert Decimal to string for JSON serialization
            'pharmacy_id': med.pharmacist.id,
            'pharmacy_name': med.pharmacist.pharmacy_name
        }
    
    # Add medicine availability information (using actual extracted medicines)
    for prescription in all_prescriptions:
        prescription.medicine_matches = []
        prescription.unavailable_medicines = []
        
        # Use extracted medicines from the prescription
        extracted_medicines = prescription.extracted_medicines or []
        
        for medicine in extracted_medicines:
            med_name = medicine['name'].lower().strip()
            if med_name in medicine_dict:
                prescription.medicine_matches.append({
                    'name': medicine_dict[med_name]['medicine'].generic_name,
                    'brand': medicine_dict[med_name]['medicine'].brand_name,
                    'stock': medicine_dict[med_name]['stock'],
                    'price': medicine_dict[med_name]['price'],
                    'strength': medicine_dict[med_name]['medicine'].strength,
                    'pharmacy_id': medicine_dict[med_name]['pharmacy_id'],
                    'pharmacy_name': medicine_dict[med_name]['pharmacy_name'],
                    'extracted_info': medicine
                })
            else:
                prescription.unavailable_medicines.append({
                    'name': medicine['name'],
                    'reason': 'Not stocked by this pharmacy',
                    'extracted_info': medicine
                })
    
    context = {
        'user': pharmacist,
        'prescriptions': all_prescriptions,
        'cart_count': 0,  # Pharmacist doesn't use cart
    }
    
    return render(request, 'pharmacist/prescription_uploads.html', context)

def download_prescription_pdf(request, prescription_id):
    """Generate and download a prescription PDF for patients"""
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
        prescription = Prescription.objects.select_related('doctor', 'patient', 'appointment').prefetch_related('medicines').get(
            id=prescription_id, 
            patient=patient
        )
    except (Patient.DoesNotExist, Prescription.DoesNotExist):
        return redirect('patient_prescriptions')
    
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from io import BytesIO
    from datetime import datetime
    import os
    
    # Create a BytesIO buffer to hold the PDF
    buffer = BytesIO()
    
    # Create the PDF object using the buffer
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=15,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#1e40af'),
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=14,
        spaceAfter=20,
        alignment=1,
        textColor=colors.HexColor('#374151'),
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=8,
        textColor=colors.HexColor('#1f2937'),
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        textColor=colors.HexColor('#374151'),
        fontName='Helvetica'
    )
    
    # Prescription Header
    elements.append(Paragraph("MEDICAL PRESCRIPTION", title_style))
    elements.append(Spacer(1, 12))
    
    # Doctor Information Box
    doctor_info = [
        ["Doctor Information", ""],
        ["Name:", f"Dr. {prescription.doctor.first_name} {prescription.doctor.last_name}"],
        ["Speciality:", prescription.doctor.speciality],
        ["License Number:", prescription.doctor.license_number or "N/A"],
        ["Clinic/Hospital:", prescription.doctor.cureentHospital or "Private Practice"],
    ]
    
    doctor_table = Table(doctor_info, colWidths=[100*mm, 70*mm])
    doctor_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dbeafe')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    
    elements.append(doctor_table)
    elements.append(Spacer(1, 15))
    
    # Patient Information Box
    patient_info = [
        ["Patient Information", ""],
        ["Name:", f"{prescription.patient.first_name} {prescription.patient.last_name}"],
        ["Date of Birth:", prescription.patient.date_of_birth.strftime('%B %d, %Y') if prescription.patient.date_of_birth else "N/A"],
        ["Gender:", prescription.patient.gender.capitalize() if prescription.patient.gender else "N/A"],
        ["Blood Group:", prescription.patient.blood_group.upper() if prescription.patient.blood_group else "N/A"],
        ["Prescription Date:", prescription.created_at.strftime('%B %d, %Y')],
    ]
    
    patient_table = Table(patient_info, colWidths=[100*mm, 70*mm])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fee2e2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#991b1b')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fff5f5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#fecaca')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    
    elements.append(patient_table)
    elements.append(Spacer(1, 20))
    
    # Medicines Section
    elements.append(Paragraph("PRESCRIBED MEDICATIONS", header_style))
    elements.append(Spacer(1, 10))
    
    # Medicines table header
    medicine_header = ['Medicine', 'Strength', 'Dosage', 'Quantity', 'Duration']
    medicine_data = [medicine_header]
    
    # Add medicines data
    for medicine in prescription.medicines.all():
        medicine_row = [
            f"{medicine.drug_name_generic}{(' (' + medicine.drug_name_brand + ')') if medicine.drug_name_brand else ''}",
            medicine.strength,
            medicine.dosage_frequency,
            medicine.total_quantity,
            medicine.duration_course
        ]
        medicine_data.append(medicine_row)
    
    # Create medicines table
    if len(medicine_data) > 1:  # If there are medicines
        medicine_table = Table(medicine_data, colWidths=[60*mm, 25*mm, 35*mm, 25*mm, 25*mm])
        medicine_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(medicine_table)
    else:
        elements.append(Paragraph("No medications prescribed.", normal_style))
    
    elements.append(Spacer(1, 15))
    
    # Instructions section
    if prescription.medicines.exists():
        elements.append(Paragraph("SPECIAL INSTRUCTIONS", header_style))
        elements.append(Spacer(1, 8))
        
        # Collect all instructions
        all_instructions = []
        for medicine in prescription.medicines.all():
            if medicine.instructions:
                instruction_text = f"• {medicine.drug_name_generic}: {medicine.instructions}"
                all_instructions.append(instruction_text)
        
        if all_instructions:
            instructions_para = Paragraph("<br/>".join(all_instructions), normal_style)
            elements.append(instructions_para)
        else:
            elements.append(Paragraph("No special instructions provided.", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # Signature section
    signature_data = [
        ["", ""],
        [f"Dr. {prescription.doctor.first_name} {prescription.doctor.last_name}", ""],
        [prescription.doctor.speciality, ""],
        ["Signature", "Date: " + prescription.created_at.strftime('%m/%d/%Y')],
    ]
    
    signature_table = Table(signature_data, colWidths=[100*mm, 70*mm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, 2), 'Helvetica-Bold'),
        ('FONTNAME', (1, 3), (1, 3), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 1), (0, 1), 1, colors.black),
        ('LINEBELOW', (1, 3), (1, 3), 1, colors.black),
    ]))
    
    elements.append(signature_table)
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="prescription_{prescription.id}_{prescription.created_at.strftime("%Y%m%d")}.pdf"'
    
    return response

def patient_notifications(request):
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Mark all unread notifications as read and update their read_at timestamp
    from django.utils import timezone
    from datetime import timedelta
    
    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    context = {
        'user': patient,
        'notifications': notifications,
        'cart_count': cart_count,
    }
    return render(request, 'patient/notifications.html', context)

def view_doctors(request):
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=user_id)
    
    # Handle search functionality
    search_query = request.GET.get('search', '')
    specialization_filter = request.GET.get('specialization', '')
    
    doctors = Doctor.objects.all()
    
    if search_query:
        doctors = doctors.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if specialization_filter:
        doctors = doctors.filter(speciality__icontains=specialization_filter)
    
    doctors = doctors.order_by('speciality', 'first_name')
    
    # Get patient's appointments for recent appointments section
    recent_appointments = Appointment.objects.filter(patient=patient).prefetch_related('reviews').order_by('-created_at')
    
    # Create a dictionary mapping doctor IDs to their latest completed appointment
    completed_appointments_map = {}
    for appointment in recent_appointments:
        if appointment.status == 'completed':
            # Only store the latest completed appointment per doctor
            if appointment.doctor.id not in completed_appointments_map:
                completed_appointments_map[str(appointment.doctor.id)] = appointment
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    # Get all unique specializations for the filter dropdown
    specializations = Doctor.objects.values_list('speciality', flat=True).distinct().order_by('speciality')
    
    context = {
        'user': patient,
        'doctors': doctors,
        'appointments': recent_appointments,
        'completed_appointments_map': completed_appointments_map,
        'notifications': notifications,
        'cart_count': cart_count,
        'search_query': search_query,
        'specialization_filter': specialization_filter,
        'specializations': specializations
    }
    return render(request, 'patient/doctors.html', context)

def book_appointment(request, doctor_id):
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=user_id)
    doctor = Doctor.objects.get(id=doctor_id)
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    if request.method == 'POST':
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        reason = request.POST.get('reason')
        
        Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason_for_visit=reason
        )
        messages.success(request, f'Appointment booked successfully with Dr. {doctor.first_name} {doctor.last_name} on {appointment_date} at {appointment_time}')
        return redirect('view_doctors')
    
    context = {
        'user': patient,
        'doctor': doctor,
        'cart_count': cart_count
    }
    return render(request, 'patient/book_appointment.html', context)

def patient_appointments(request):
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=user_id)
    appointments = Appointment.objects.filter(patient=patient).prefetch_related('reviews').order_by('-created_at')
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    context = {
        'user': patient,
        'appointments': appointments,
        'notifications': notifications,
        'cart_count': cart_count
    }
    return render(request, 'patient/appointments.html', context)



def update_profile(request):
    user_id = request.session.get('patient_id')
    if not user_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=user_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    if request.method == 'POST':
        # instance=patient populates the form with existing data and maps the POST data to it
        form = PatientProfileUpdateForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully! Redirecting...")
    else:
        # This automatically pre-fills the fields with current data
        form = PatientProfileUpdateForm(instance=patient)
    
    # Get notifications for the patient, excluding those read more than 2 days ago
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    # Mark all unread notifications as read and update their read_at timestamp
    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')[:5]
    
    return render(request, 'patient/profile.html', {
        'form': form, 
        'user': patient,
        'notifications': notifications,
        'cart_count': cart_count
    })



def admin_profile(request):
    admin_id = request.session.get('admin_id')
    
    if not admin_id:
        return redirect('login')
    
    try:
        admin = MediAdmin.objects.get(id=admin_id)
    except MediAdmin.DoesNotExist:
        return redirect('login')
    
    if request.method == 'POST':
        admin.email = request.POST.get('email')
        admin.password = request.POST.get('password')
        admin.save()
        messages.success(request, "Admin profile updated successfully!")
        return redirect('admin_profile')
    else:
        context = {
            'admin': admin
        }
    return render(request, 'admin/profile.html', context)


def pharmacist_dashboard(request):
    from .models import Pharmacist  # Import here to avoid circular import
    
    pharmacist_id = request.session.get('pharmacist_id')
    
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except:
        return redirect('login')
    
    # Actual data from database
    all_medicines = Medicine.objects.filter(pharmacist=pharmacist)
    low_stock_meds = all_medicines.filter(quantity__lt=10)
    
    # Calculate real data for dashboard
    from datetime import datetime, timedelta
    from django.utils import timezone
    from django.db.models import Sum
    
    # Count today's orders for medicines from this pharmacist
    today = timezone.now().date()
    today_orders = OrderItem.objects.filter(
        medicine__pharmacist=pharmacist,
        order__created_at__date=today
    ).count()
    
    # Calculate weekly sales for this pharmacist
    week_ago = timezone.now() - timedelta(days=7)
    weekly_sales = OrderItem.objects.filter(
        medicine__pharmacist=pharmacist,
        order__created_at__gte=week_ago
    ).aggregate(total=Sum('price_at_order'))['total'] or 0
    
    # Get recent customers (patients who ordered medicines from this pharmacist recently)
    recent_orders = OrderItem.objects.filter(
        medicine__pharmacist=pharmacist
    ).select_related('order__patient').order_by('-order__created_at')[:10]
    
    # Extract unique patients from recent orders
    recent_customers = []
    seen_customers = set()
    for order_item in recent_orders:
        patient = order_item.order.patient
        customer_key = patient.id
        if customer_key not in seen_customers:
            # Determine how recent the visit was
            days_diff = (timezone.now().date() - order_item.order.created_at.date()).days
            if days_diff == 0:
                last_visit = 'Today'
            elif days_diff == 1:
                last_visit = 'Yesterday'
            else:
                last_visit = f'{days_diff} days ago'
                
            recent_customers.append({
                'name': f'{patient.first_name} {patient.last_name}',
                'contact': patient.email,
                'last_visit': last_visit
            })
            seen_customers.add(customer_key)
            if len(recent_customers) >= 3:  # Limit to 3 recent customers
                break
    
    dashboard_data = {
        'medications_low_stock': low_stock_meds.count(),
        'today_orders': today_orders,
        'weekly_sales': round(weekly_sales, 2),  # Round to 2 decimal places
        'recent_customers': recent_customers,
        'low_stock_medications': [
            {'name': med.generic_name, 'quantity': med.quantity} for med in low_stock_meds[:5]
        ]
    }
    
    context = {
        'pharmacist': pharmacist,
        'data': dashboard_data
    }
    return render(request, 'pharmacist/dashboard.html', context)


def pharmacist_profile(request):
    
    pharmacist_id = request.session.get('pharmacist_id')
    
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except:
        return redirect('login')
    
    if request.method == 'POST':
        form = PharmacistProfileUpdateForm(request.POST, instance=pharmacist)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('pharmacist_profile')
    else:
        form = PharmacistProfileUpdateForm(instance=pharmacist)
    
    # Pass password value for display as dots
    context = {
        'pharmacist': pharmacist,
        'form': form,
        'has_password': bool(pharmacist.password and pharmacist.password.strip()),
        'current_password': pharmacist.password if pharmacist.password else ''
    }
    return render(request, 'pharmacist/profile.html', context)


def pharmacist_inventory(request):
    from django.utils import timezone
    from datetime import timedelta
    
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        return redirect('login')
    
    if request.method == 'POST':
        form = MedicineForm(request.POST)
        if form.is_valid():
            medicine = form.save(commit=False)
            medicine.pharmacist = pharmacist
            medicine.save()
            messages.success(request, "Medicine added to inventory successfully!")
            return redirect('pharmacist_inventory')
    else:
        form = MedicineForm()
    
    # Logic to hide products within 3-6 months of expiry
    # We'll hide everything expiring within 6 months (180 days)
    six_months_from_now = timezone.now().date() + timedelta(days=180)
    
    all_medicines = Medicine.objects.filter(pharmacist=pharmacist).order_by('-created_at')
    visible_medicines = all_medicines.exclude(expiry_date__lte=six_months_from_now)
    hidden_count = all_medicines.filter(expiry_date__lte=six_months_from_now).count()
    
    context = {
        'pharmacist': pharmacist,
        'medicines': visible_medicines,
        'form': form,
        'hidden_count': hidden_count
    }
    return render(request, 'pharmacist/inventory.html', context)

def edit_medicine(request, pk):
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    medicine = Medicine.objects.filter(id=pk, pharmacist_id=pharmacist_id).first()
    if not medicine:
        messages.error(request, "Medicine not found.")
        return redirect('pharmacist_inventory')
    
    if request.method == 'POST':
        form = MedicineForm(request.POST, instance=medicine)
        if form.is_valid():
            form.save()
            messages.success(request, "Medicine updated successfully!")
        else:
            messages.error(request, "Error updating medicine.")
            
    return redirect('pharmacist_inventory')

def pharmacist_orders(request):
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        return redirect('login')
    
    # Get medicines belonging to this pharmacist
    pharmacist_medicines = Medicine.objects.filter(pharmacist=pharmacist)
    
    # Get orders that contain these medicines through OrderItem
    from django.db.models import Prefetch
    orders = Order.objects.filter(
        items__medicine__in=pharmacist_medicines
    ).distinct().prefetch_related(
        Prefetch('items', queryset=OrderItem.objects.select_related('medicine')),
        'patient'
    ).order_by('-created_at')
    
    # Calculate statistics
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    successful_orders = orders.filter(status='successful').count()
    failed_orders = orders.filter(status='failed').count()
    delayed_orders = orders.filter(status='delayed').count()
    
    context = {
        'pharmacist': pharmacist,
        'orders': orders,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'successful_orders': successful_orders,
        'failed_orders': failed_orders,
        'delayed_orders': delayed_orders,
    }
    
    return render(request, 'pharmacist/orders.html', context)

def pharmacist_customers(request):
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        return redirect('login')
    
    # Get all patients who have ordered medicines from this pharmacist
    customer_ids = OrderItem.objects.filter(
        medicine__pharmacist=pharmacist
    ).values_list('order__patient', flat=True).distinct()
    
    patients = Patient.objects.filter(id__in=customer_ids)
    
    # For each patient, get their recent prescriptions
    patient_data = []
    for patient in patients:
        # Get prescriptions related to medicines ordered from this pharmacist
        prescriptions = Prescription.objects.filter(
            patient=patient,
            appointment__in=Appointment.objects.filter(patient=patient)
        ).select_related('doctor', 'appointment').order_by('-created_at')
        
        # Get order items for this patient that have course duration
        order_items = OrderItem.objects.filter(
            order__patient=patient,
            medicine__pharmacist=pharmacist,
            course_duration__isnull=False
        ).select_related('medicine', 'order')
        
        # Also get related prescriptions for this patient
        patient_prescriptions = Prescription.objects.filter(patient=patient).select_related('doctor', 'appointment').prefetch_related('medicines')
        
        patient_data.append({
            'patient': patient,
            'prescriptions': prescriptions,
            'order_items': order_items,
            'patient_prescriptions': patient_prescriptions
        })
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient__in=Patient.objects.all()).count()  # Count for all patients
    
    return render(request, 'pharmacist/customers.html', {
        'user': pharmacist,
        'patient_data': patient_data,
        'cart_count': cart_count
    })

def send_refill_reminder(request, order_item_id):
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
        order_item = OrderItem.objects.get(id=order_item_id)
        
        # Verify that this order item belongs to a medicine from this pharmacist
        if order_item.medicine.pharmacist != pharmacist:
            messages.error(request, "You don't have permission to send reminders for this order.")
            return redirect('pharmacist_customers')
        
        # Check if reminder has already been sent
        if order_item.reminder_sent_at is not None:
            messages.warning(request, f"Reminder already sent for {order_item.medicine.brand_name} on {order_item.reminder_sent_at.strftime('%Y-%m-%d')}.")
            return redirect('pharmacist_customers')
        
        # Parse the course duration to calculate when supply will run out
        import re
        duration_text = order_item.course_duration or ""
        days_match = re.search(r'(\d+)', duration_text)
        
        if days_match:
            try:
                duration_days = int(days_match.group(1))
                estimated_end_date = order_item.order.created_at.date() + timedelta(days=duration_days)
                
                # Calculate how much is left based on current date
                days_remaining = (estimated_end_date - timezone.now().date()).days
                
                # Calculate when the current supply will run out
                duration_text = order_item.course_duration or ""
                days_match = re.search(r'(\d+)', duration_text)
                
                if days_match:
                    duration_days = int(days_match.group(1))
                    estimated_end_date = order_item.order.created_at.date() + timedelta(days=duration_days)
                    
                    # Calculate how much of the original prescription remains
                    days_remaining = (estimated_end_date - timezone.now().date()).days
                    
                    # Create a more specific message as requested
                    # Try to find the original prescription to get the full duration
                    try:
                        # Look for related prescriptions
                        related_prescription = Prescription.objects.filter(
                            patient=order_item.order.patient,
                            drug_name_generic=order_item.medicine.generic_name,
                            appointment__in=Appointment.objects.filter(patient=order_item.order.patient)
                        ).first()
                        
                        if related_prescription:
                            # Extract total duration from prescription
                            presc_days_match = re.search(r'(\d+)', related_prescription.duration_course or "")
                            if presc_days_match:
                                presc_total_days = int(presc_days_match.group(1))
                                
                                # Calculate how much has been used vs remaining
                                days_used = duration_days
                                days_left_from_prescription = presc_total_days - days_used
                                
                                if days_left_from_prescription > 0:
                                    message = f'Your {order_item.course_duration} supply of {order_item.medicine.brand_name} is ending soon. As per your doctor\'s {related_prescription.duration_course} prescription, please order your remaining {days_left_from_prescription}-day supply.'
                                else:
                                    message = f'Your {order_item.course_duration} supply of {order_item.medicine.brand_name} is ending soon. As per your doctor\'s {related_prescription.duration_course} prescription, please consider ordering a refill.'
                            else:
                                message = f'Your {order_item.course_duration} supply of {order_item.medicine.brand_name} is ending soon. As per your doctor\'s prescription, please consider ordering a refill.'
                        else:
                            message = f'Your {order_item.course_duration} supply of {order_item.medicine.brand_name} is ending soon. As per your doctor\'s prescription, please consider ordering a refill.'
                    except:
                        message = f'Your {order_item.course_duration} supply of {order_item.medicine.brand_name} is ending soon. As per your doctor\'s prescription, please consider ordering a refill.'
                else:
                    message = f'Your supply of {order_item.medicine.brand_name} is ending soon. As per your doctor\'s prescription, please consider ordering a refill.'
                
                Notification.objects.create(
                    patient=order_item.order.patient,
                    notification_type='refill_reminder',
                    title='Medicine Supply Ending Soon',
                    message=message,
                    related_id=order_item.id
                )
                
                # Update the reminder_sent_at timestamp
                order_item.reminder_sent_at = timezone.now()
                order_item.save()
                
                messages.success(request, f"Refill reminder sent successfully for {order_item.medicine.brand_name}.")
                
            except ValueError:
                messages.error(request, f"Could not parse duration for {order_item.medicine.brand_name}. Please check the course duration format.")
        else:
            messages.error(request, f"Could not determine duration for {order_item.medicine.brand_name}. Course duration format is unrecognized.")
        
    except Pharmacist.DoesNotExist:
        messages.error(request, "Pharmacist not found.")
    except OrderItem.DoesNotExist:
        messages.error(request, "Order item not found.")
    
    return redirect('pharmacist_customers')

def submit_rating(request, appointment_id=None, order_id=None):
    if request.method != 'POST':
        if appointment_id:
            return redirect('view_doctors')
        elif order_id:
            return redirect('patient_orders')
        else:
            return redirect('view_doctors')
    
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=patient_id)
        
        # Get rating and review from form
        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text', '')
        
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            if appointment_id:
                # Handle appointment rating
                appointment = Appointment.objects.get(id=appointment_id, patient=patient, status='completed')
                
                # Check if patient has already reviewed this appointment
                existing_review = Review.objects.filter(patient=patient, appointment=appointment).first()
                
                if existing_review:
                    # Update existing review
                    existing_review.rating = int(rating)
                    existing_review.review_text = review_text
                    existing_review.save()
                    messages.success(request, "Your rating and review have been updated!")
                else:
                    # Create new review
                    Review.objects.create(
                        patient=patient,
                        review_type='doctor',
                        doctor=appointment.doctor,
                        appointment=appointment,
                        rating=int(rating),
                        review_text=review_text
                    )
                    messages.success(request, "Thank you for your rating and review!")
            elif order_id:
                # Handle order rating
                order = Order.objects.get(id=order_id, patient=patient, status='successful')
                
                # Check if patient has already reviewed this order
                existing_review = Review.objects.filter(patient=patient, order=order).first()
                
                if existing_review:
                    # Update existing review
                    existing_review.rating = int(rating)
                    existing_review.review_text = review_text
                    existing_review.save()
                    messages.success(request, "Your rating and review for the order have been updated!")
                else:
                    # Create new review
                    Review.objects.create(
                        patient=patient,
                        review_type='order',
                        order=order,
                        rating=int(rating),
                        review_text=review_text
                    )
                    messages.success(request, "Thank you for your rating and review for the order!")
        else:
            messages.error(request, "Please select a valid rating (1-5 stars).")
            
    except (Patient.DoesNotExist, Appointment.DoesNotExist, Order.DoesNotExist):
        messages.error(request, "Item not found.")
    
    if appointment_id:
        return redirect('view_doctors')
    elif order_id:
        return redirect('patient_orders')
    else:
        return redirect('view_doctors')

def update_order_status(request, order_id):
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    if request.method != 'POST':
        return redirect('pharmacist_orders')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
        order = Order.objects.get(id=order_id)
        
        # Verify that this order contains medicines from this pharmacist
        pharmacist_medicines = Medicine.objects.filter(pharmacist=pharmacist)
        order_items = OrderItem.objects.filter(order=order, medicine__in=pharmacist_medicines)
        
        if not order_items.exists():
            messages.error(request, "You don't have permission to update this order.")
            return redirect('pharmacist_orders')
        
        # Update status
        new_status = request.POST.get('status')
        if new_status in dict(Order.ORDER_STATUS).keys():
            old_status = order.status
            order.status = new_status
            order.save()
            

            
            messages.success(request, f"Order #{order.id} status updated to {order.get_status_display()}.")
        else:
            messages.error(request, "Invalid status selected.")
            
    except (Pharmacist.DoesNotExist, Order.DoesNotExist):
        messages.error(request, "Order not found.")
    
    return redirect('pharmacist_orders')

def pharmacist_ratings_feedback(request):
    from django.db.models import Avg
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    
    # Get all medicines from this pharmacist
    pharmacist_medicines = Medicine.objects.filter(pharmacist=pharmacist)
    
    # Get all orders that contain medicines from this pharmacist
    order_ids = OrderItem.objects.filter(medicine__in=pharmacist_medicines).values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids).select_related('patient').order_by('-created_at')
    
    # Get reviews for orders that contain medicines from this pharmacist
    reviews = Review.objects.filter(
        order__in=orders,
        review_type='order'
    ).select_related('patient', 'order').order_by('-created_at')
    
    # Calculate stats
    total_reviews = reviews.count()
    average_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
    if average_rating:
        average_rating = round(average_rating, 2)
    else:
        average_rating = 0
    
    positive_reviews = reviews.filter(rating__gte=4).count()
    
    context = {
        'pharmacist': pharmacist,
        'reviews': reviews,
        'total_reviews': total_reviews,
        'average_rating': average_rating,
        'positive_reviews': positive_reviews,
    }
    return render(request, 'pharmacist/ratings_feedback.html', context)

def doctor_dashboard(request):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
    except Doctor.DoesNotExist:
        return redirect('login')
    
    # Check profile completion (customize as needed)
    required_fields = [doctor.description, doctor.profile_picture, doctor.cureentHospital, doctor.license_number, doctor.address]
    profile_incomplete = any(field in [None, '', 'None'] for field in required_fields)
    
    # Calculate real data for dashboard
    from datetime import datetime, timedelta
    from django.utils import timezone
    from django.db.models import Count, Avg
    
    # Get today's date for calculating today's appointments
    today = timezone.now().date()
    
    # Count today's appointments
    today_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=today
    ).count()
    
    # Calculate average patient rating
    doctor_reviews = Review.objects.filter(doctor=doctor)
    avg_rating = doctor_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
    avg_rating = round(avg_rating, 1)
    
    # Calculate total consultations (completed appointments)
    total_consultations = Appointment.objects.filter(
        doctor=doctor,
        status='completed'
    ).count()
    
    # Get upcoming appointments for today
    upcoming_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=today
    ).select_related('patient').order_by('appointment_time')[:2]
    
    # Calculate pending reports (unreviewed prescriptions)
    pending_reports = Prescription.objects.filter(
        doctor=doctor,
        created_at__gte=timezone.now()-timedelta(days=7)  # Last 7 days
    ).count()
    
    # Get recent reviews
    recent_reviews = Review.objects.filter(
        doctor=doctor
    ).select_related('patient').order_by('-created_at')[:3]
    
    # Get current month appointments for calendar
    from datetime import datetime
    import calendar
    
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    # Get all appointments for current month
    monthly_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__month=current_month,
        appointment_date__year=current_year
    ).values_list('appointment_date', flat=True)
    
    # Create calendar data
    cal = calendar.monthcalendar(current_year, current_month)
    month_name = calendar.month_name[current_month]
    
    # Prepare appointment days
    appointment_days = set()
    for appt_date in monthly_appointments:
        appointment_days.add(appt_date.day)
    
    context = {
        'user': doctor,
        'profile_incomplete': profile_incomplete,
        'now': timezone.now(),
        'today_appointments': today_appointments,
        'avg_rating': avg_rating,
        'total_consultations': total_consultations,
        'upcoming_appointments': upcoming_appointments,
        'pending_reports': pending_reports,
        'recent_reviews': recent_reviews,
        'calendar_data': cal,
        'current_month': month_name,
        'current_year': current_year,
        'appointment_days': appointment_days,
        'today': today,
    }
    return render(request, 'doctor/dashboard.html', context)

def doctor_ratings_feedback(request):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
    except Doctor.DoesNotExist:
        return redirect('login')
    
    # Get all reviews for this doctor
    reviews = Review.objects.filter(doctor=doctor).select_related('patient', 'appointment').order_by('-created_at')
    
    # Calculate average rating
    avg_rating = 0
    if reviews.exists():
        total_rating = sum(review.rating for review in reviews)
        avg_rating = round(total_rating / reviews.count(), 1)
    
    # Count positive reviews (4-5 stars)
    positive_reviews_count = reviews.filter(rating__gte=4).count()
    
    context = {
        'user': doctor,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'positive_reviews_count': positive_reviews_count,
    }
    return render(request, 'doctor/ratings_feedback.html', context)

def doctor_profile(request):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
    except Doctor.DoesNotExist:
        return redirect('login')
    
    from .forms import DoctorProfileUpdateForm
    
    if request.method == 'POST':
        print(f"POST data keys: {list(request.POST.keys())}")
        print(f"FILES data keys: {list(request.FILES.keys())}")
        
        form = DoctorProfileUpdateForm(request.POST, request.FILES, instance=doctor)
        if form.is_valid():
            saved_doctor = form.save()
            return redirect('doctor_profile')
        else:
            print(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = DoctorProfileUpdateForm(instance=doctor)
    
    # Pass password value for display as dots and profile picture status
    context = {
        'form': form, 
        'user': doctor,
        'has_password': bool(doctor.password and doctor.password.strip()),
        'current_password': doctor.password if doctor.password else '',
        'has_profile_picture': bool(doctor.profile_picture)
    }
    return render(request, 'doctor/profile.html', context)

def doctor_appointments(request):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
    except Doctor.DoesNotExist:
        return redirect('login')
    
    # Get all appointments for this doctor, excluding completed ones
    appointments = Appointment.objects.filter(
        doctor=doctor
    ).exclude(status='completed').order_by('-created_at')
    
    context = {
        'user': doctor,
        'appointments': appointments
    }
    return render(request, 'doctor/appointments.html', context)

def update_appointment_status(request, appointment_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        appointment = Appointment.objects.get(id=appointment_id, doctor=doctor)
    except (Doctor.DoesNotExist, Appointment.DoesNotExist):
        messages.error(request, "Appointment not found.")
        return redirect('doctor_appointments')
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        # Get valid status choices from the model
        valid_statuses = [choice[0] for choice in Appointment.STATUS_CHOICES]
        if new_status in valid_statuses:
            old_status = appointment.status
            appointment.status = new_status
            appointment.save()
            
            # Create notification for patient about status update
            from .models import Notification
            Notification.objects.create(
                patient=appointment.patient,
                notification_type='appointment',
                title=f'Appointment Status Updated',
                message=f'Your appointment with Dr. {doctor.first_name} {doctor.last_name} has been updated from {old_status} to {new_status}.',
                related_id=appointment.id
            )
            
            messages.success(request, f"Appointment status updated to {appointment.get_status_display()}.")
        else:
            messages.error(request, "Invalid status selected.")
    
    # Redirect back to the referring page or default to appointments page
    redirect_url = request.POST.get('redirect_url', 'doctor_appointments')
    return redirect(redirect_url)

def reschedule_appointment(request, appointment_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        appointment = Appointment.objects.get(id=appointment_id, doctor=doctor)
    except (Doctor.DoesNotExist, Appointment.DoesNotExist):
        messages.error(request, "Appointment not found.")
        return redirect('doctor_appointments')
    
    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        new_time = request.POST.get('new_time')
        
        if new_date and new_time:
            # Update the appointment date and time
            appointment.appointment_date = new_date
            appointment.appointment_time = new_time
            appointment.status = 'scheduled'  # Reset status to scheduled after rescheduling
            appointment.save()
            messages.success(request, f"Appointment rescheduled to {new_date} at {new_time}.")
        else:
            messages.error(request, "Please provide both date and time for rescheduling.")
    
    return redirect('doctor_appointments')


def doctor_patients(request):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
    except Doctor.DoesNotExist:
        return redirect('login')
    
    # Get all completed appointments for this doctor's patients
    completed_appointments = Appointment.objects.filter(
        doctor=doctor,
        status='completed'
    ).select_related('patient').prefetch_related('reviews')
    
    # Get all prescriptions for this doctor's patients with their medicines
    prescriptions = Prescription.objects.filter(doctor=doctor).select_related('patient', 'appointment').prefetch_related('medicines')
    
    context = {
        'user': doctor,
        'completed_appointments': completed_appointments,
        'prescriptions': prescriptions,
    }
    return render(request, 'doctor/patients.html', context)


def add_prescription(request, appointment_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        appointment = Appointment.objects.get(id=appointment_id, doctor=doctor)
    except (Doctor.DoesNotExist, Appointment.DoesNotExist):
        messages.error(request, "Appointment not found.")
        return redirect('doctor_patients')
    
    # Check if there's a prescription to copy (prefill)
    original_prescription = request.GET.get('copy')
    original_medicines = []
    if original_prescription:
        try:
            original_prescription_obj = Prescription.objects.get(id=original_prescription, doctor=doctor)
            original_medicines = original_prescription_obj.medicines.all()
        except Prescription.DoesNotExist:
            original_prescription_obj = None
    
    if request.method == 'POST':
        # Create a new prescription
        prescription = Prescription.objects.create(
            appointment=appointment,
            doctor=doctor,
            patient=appointment.patient,
        )
        
        # Process multiple medicines
        medicine_count = int(request.POST.get('medicine_count', 0))
        medicines_added = 0
        
        for i in range(medicine_count):
            # Check if this medicine row has data
            drug_name_generic = request.POST.get(f'medicine_{i}_drug_name_generic', '').strip()
            if drug_name_generic:  # Only create medicine if generic name is provided
                PrescriptionMedicine.objects.create(
                    prescription=prescription,
                    drug_name_generic=drug_name_generic,
                    strength=request.POST.get(f'medicine_{i}_strength', ''),
                    dosage_frequency=request.POST.get(f'medicine_{i}_dosage_frequency', ''),
                    route_administration=request.POST.get(f'medicine_{i}_route_administration', ''),
                    instructions=request.POST.get(f'medicine_{i}_instructions', ''),
                    total_quantity=request.POST.get(f'medicine_{i}_total_quantity', ''),
                    duration_course=request.POST.get(f'medicine_{i}_duration_course', ''),
                )
                medicines_added += 1
        
        if medicines_added > 0:
            messages.success(request, f"Prescription with {medicines_added} medicine(s) added successfully!")
        else:
            messages.error(request, "No medicines were added. Please add at least one medicine.")
            prescription.delete()  # Clean up empty prescription
            return redirect('add_prescription', appointment_id=appointment_id)
            
        return redirect('doctor_patients')
    
    context = {
        'user': doctor,
        'appointment': appointment,
        'original_prescription': original_prescription,
        'original_medicines': original_medicines,
    }
    return render(request, 'doctor/add_prescription.html', context)


def patient_prescriptions_by_doctor(request, patient_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        patient = Patient.objects.get(id=patient_id)
        # Get all prescriptions for this patient by this doctor with their medicines
        prescriptions = Prescription.objects.filter(
            patient=patient,
            doctor=doctor
        ).prefetch_related('medicines').order_by('-created_at')
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return redirect('doctor_patients')
    
    context = {
        'prescriptions': prescriptions,
        'patient': patient,
    }
    return render(request, 'doctor/patient_prescriptions_modal.html', context)


def copy_prescription(request, prescription_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        original_prescription = Prescription.objects.get(id=prescription_id, doctor=doctor)
    except (Doctor.DoesNotExist, Prescription.DoesNotExist):
        messages.error(request, "Prescription not found.")
        return redirect('doctor_patients')
    
    # Redirect to add prescription page with pre-filled data
    from django.urls import reverse
    from urllib.parse import urlencode
    
    url = reverse('add_prescription', kwargs={'appointment_id': original_prescription.appointment.id})
    url += '?' + urlencode({'copy': original_prescription.id})
    return redirect(url)


def delete_prescription(request, prescription_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        prescription = Prescription.objects.get(id=prescription_id, doctor=doctor)
        
        # Delete the prescription (this will cascade delete related PrescriptionMedicine objects)
        prescription.delete()
        
        return JsonResponse({'success': True, 'message': 'Prescription deleted successfully'})
        
    except Doctor.DoesNotExist:
        return JsonResponse({'error': 'Doctor not found'}, status=404)
    except Prescription.DoesNotExist:
        return JsonResponse({'error': 'Prescription not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def register(request):
    # Initialize empty forms for a GET request
    patient_form = PatientRegistrationForm()
    pharmacist_form = PharmacistRegistrationForm()
    registered = False
    
    if request.method == 'POST':
        role = request.POST.get('role')
        
        if role == 'patient':
            patient_form = PatientRegistrationForm(request.POST)
            if patient_form.is_valid():
                user_role = Users.objects.create(role='patient')
                patient = patient_form.save(commit=False)
                patient.user = user_role
                patient.save()
                registered = True
            # If invalid, patient_form now contains error data
                
        elif role == 'pharmacist':
            pharmacist_form = PharmacistRegistrationForm(request.POST)
            if pharmacist_form.is_valid():
                user_role = Users.objects.create(role='pharmacist')
                pharmacist = pharmacist_form.save(commit=False)
                pharmacist.user = user_role
                pharmacist.save()
                registered = True
            # If invalid, pharmacist_form now contains error data

    # This context now contains the forms with their respective errors
    context = {
        'patient_form': patient_form,
        'pharmacist_form': pharmacist_form,
        'registered': registered
    }
    return render(request, 'register.html', context)

def manage_doctors(request):
    # Ensure admin authentication
    if not request.session.get('admin_id'):
        return redirect('login')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            form = DoctorRegistrationForm(request.POST)
            if form.is_valid():
                # Create base User entry first (if your logic requires it for doctors too)
                # Assuming Doctors also need a Users entry like Patients/Pharmacists
                user_role = Users.objects.create(role='doctor')
                
                doctor = form.save(commit=False)
                doctor.user = user_role
                doctor.save()
                messages.success(request, "Doctor added successfully!")
            else:
                messages.error(request, "Error adding doctor. Please check the form.")
                
        elif action == 'edit':
            doctor_id = request.POST.get('doctor_id')
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                form = DoctorRegistrationForm(request.POST, instance=doctor)
                # Password is optional in edit if left blank, but form might require it. 
                # For simplicity here, we assume full update or handled by form logic.
                if form.is_valid():
                    form.save()
                    messages.success(request, "Doctor updated successfully!")
                else:
                    messages.error(request, "Error updating doctor.")
            except Doctor.DoesNotExist:
                messages.error(request, "Doctor not found.")
                
        elif action == 'delete':
            doctor_id = request.POST.get('doctor_id')
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                if doctor.user:
                    doctor.user.delete() # Cascade should handle doctor deletion usually, or delete both
                else:
                    doctor.delete()
                messages.success(request, "Doctor deleted successfully!")
            except Doctor.DoesNotExist:
                messages.error(request, "Doctor not found.")
                
        return redirect('manage_doctors')
        
    # GET request
    doctors = Doctor.objects.all().order_by('-registration_date')
    
    # Annotate each doctor with their appointment count
    from django.db.models import Count
    doctors_with_appointments = []
    for doctor in doctors:
        appointment_count = Appointment.objects.filter(doctor=doctor).count()
        doctors_with_appointments.append({
            'doctor': doctor,
            'appointment_count': appointment_count
        })
    
    form = DoctorRegistrationForm()
    
    return render(request, 'admin/doctors.html', {
        'doctors_with_appointments': doctors_with_appointments,
        'form': form
    })

def manage_patients(request):
    # Ensure admin authentication
    if not request.session.get('admin_id'):
        return redirect('login')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            patient_id = request.POST.get('patient_id')
            try:
                patient = Patient.objects.get(id=patient_id)
                if patient.user:
                    patient.user.delete()
                else:
                    patient.delete()
                messages.success(request, "Patient deleted successfully!")
            except Patient.DoesNotExist:
                messages.error(request, "Patient not found.")
        return redirect('manage_patients')

    patients = Patient.objects.all().order_by('first_name')
    return render(request, 'admin/patients.html', {'patients': patients})

def medication_management(request):
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
    
    return render(request, 'admin/medications.html', {'medicines': medicines})

def generate_report(request):
    if not request.session.get('admin_id'): return redirect('login')
    return render(request, 'admin/reports.html')

def export_medications_csv(request):
    import csv
    from django.http import HttpResponse
    
    if not request.session.get('admin_id'): return redirect('login')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="medications_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Brand Name', 'Generic Name', 'Pharmacy', 'Stock', 'Price', 'Expiry Date'])
    
    medicines = Medicine.objects.all()
    for med in medicines:
        writer.writerow([med.brand_name, med.generic_name, med.pharmacist.pharmacy_name, med.quantity, med.price, med.expiry_date])
        
    return response

def financial_oversight(request):
    if not request.session.get('admin_id'): return redirect('login')
    
    from django.db.models import Sum
    transactions = Transaction.objects.select_related('order').all().order_by('-timestamp')
    total_revenue = transactions.aggregate(total=Sum('amount'))['total'] or 0
    
    return render(request, 'admin/finance.html', {
        'transactions': transactions,
        'total_revenue': total_revenue,
        'transaction_count': transactions.count()
    })

def admin_ratings_feedback(request):
    if not request.session.get('admin_id'): return redirect('login')
    
    from django.db.models import Avg
    
    # Get all reviews
    all_reviews = Review.objects.select_related('patient', 'doctor', 'order', 'order__patient').prefetch_related('order__items__medicine__pharmacist').order_by('-created_at')
    
    # Get doctor reviews
    doctor_reviews = all_reviews.filter(review_type='doctor').select_related('doctor')
    
    # Get order reviews (for pharmacists)
    order_reviews = all_reviews.filter(review_type='order').select_related('order__patient').prefetch_related('order__items__medicine__pharmacist')
    
    # Calculate stats for doctor reviews
    total_doctor_reviews = doctor_reviews.count()
    avg_doctor_rating = doctor_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
    if avg_doctor_rating:
        avg_doctor_rating = round(avg_doctor_rating, 2)
    else:
        avg_doctor_rating = 0
    positive_doctor_reviews = doctor_reviews.filter(rating__gte=4).count()
    
    # Calculate stats for order reviews
    total_order_reviews = order_reviews.count()
    avg_order_rating = order_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
    if avg_order_rating:
        avg_order_rating = round(avg_order_rating, 2)
    else:
        avg_order_rating = 0
    positive_order_reviews = order_reviews.filter(rating__gte=4).count()
    
    # Combine all reviews sorted by date
    all_reviews_sorted = sorted(list(doctor_reviews) + list(order_reviews), key=lambda x: x.created_at, reverse=True)
    
    # Add unique pharmacists to order reviews
    for review in all_reviews_sorted:
        if review.review_type == 'order' and hasattr(review, 'order') and review.order:
            pharmacists_set = set()
            for item in review.order.items.all():
                if item.medicine.pharmacist:
                    pharmacists_set.add(item.medicine.pharmacist)
            review.unique_pharmacists = list(pharmacists_set)
    
    context = {
        'all_reviews': all_reviews_sorted,
        'doctor_reviews': doctor_reviews,
        'order_reviews': order_reviews,
        'total_doctor_reviews': total_doctor_reviews,
        'avg_doctor_rating': avg_doctor_rating,
        'positive_doctor_reviews': positive_doctor_reviews,
        'total_order_reviews': total_order_reviews,
        'avg_order_rating': avg_order_rating,
        'positive_order_reviews': positive_order_reviews,
    }
    return render(request, 'admin/ratings_feedback.html', context)


def export_patient_registry_pdf(request):
    if not request.session.get('admin_id'): return redirect('login')
    
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from io import BytesIO
    
    # Create a BytesIO buffer to hold the PDF
    buffer = BytesIO()
    
    # Create the PDF object using the buffer
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=(0.73, 0.12, 0.21)  # Rose color
    )
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=14,
        textColor=(0.4, 0.4, 0.4),
        spaceAfter=5,
    )
    
    # Title
    title = Paragraph("Patient Registry Report", title_style)
    elements.append(title)
    
    # Date
    from datetime import datetime
    date_para = Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", header_style)
    elements.append(date_para)
    elements.append(Spacer(1, 20))
    
    # Patient data
    patients = Patient.objects.all().order_by('last_name', 'first_name')
    
    if patients.exists():
        # Table headers
        data = [['Patient ID', 'Name', 'Phone', 'Email', 'Gender', 'Date of Birth', 'Blood Group', 'Address']]
        
        # Add patient data
        for patient in patients:
            dob = patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else 'N/A'
            email = patient.email if patient.email else 'N/A'
            phone = patient.phone_number if patient.phone_number else 'N/A'
            gender = patient.gender if patient.gender else 'N/A'
            blood_group = patient.blood_group if patient.blood_group else 'N/A'
            address = patient.address if patient.address else 'N/A'
            
            data.append([
                str(patient.id),
                f"{patient.first_name} {patient.last_name}",
                phone,
                email,
                gender,
                dob,
                blood_group,
                address
            ])
        
        # Create table
        table = Table(data)
        
        # Style the table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),  # Header background
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#64748b')),     # Header text color
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),                           # Left align all cells
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),               # Bold header
            ('FONTSIZE', (0, 0), (-1, 0), 10),                            # Header font size
            ('FONTSIZE', (0, 1), (-1, -1), 9),                            # Body font size
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),                       # Header padding
            ('TOPPADDING', (0, 0), (-1, 0), 12),                          # Header padding
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),                       # Body padding
            ('TOPPADDING', (0, 1), (-1, -1), 8),                          # Body padding
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),    # Grid lines
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),                       # Vertical alignment
        ]))
        
        elements.append(table)
        
        # Add patient count summary
        elements.append(Spacer(1, 20))
        summary_text = f"Total Patients Registered: {patients.count()}"
        summary_para = Paragraph(summary_text, header_style)
        elements.append(summary_para)
    else:
        # No patients message
        no_patients = Paragraph("No patients found in the registry.", header_style)
        elements.append(no_patients)
    
    # Build the PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="patient_registry_report.pdf"'
    return response


def export_financial_summary_xlsx(request):
    if not request.session.get('admin_id'): return redirect('login')
    
    import pandas as pd
    from django.http import HttpResponse
    from io import BytesIO
    
    # Get financial data
    from .models import Transaction, Order
    from django.db.models import Sum
    from datetime import datetime
    
    transactions = Transaction.objects.all().order_by('-timestamp')
    total_revenue = transactions.aggregate(total=Sum('amount'))['total'] or 0
    
    # Prepare data for the Excel file
    data = []
    for transaction in transactions:
        data.append({
            'Transaction ID': transaction.id,
            'Amount': transaction.amount,
            'Timestamp': transaction.timestamp,
            'Description': getattr(transaction, 'description', 'N/A'),
            'Status': getattr(transaction, 'status', 'N/A')
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create a BytesIO buffer
    buffer = BytesIO()
    
    # Write DataFrame to Excel
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Write main data
        df.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Write summary sheet
        summary_data = {
            'Metric': ['Total Transactions', 'Total Revenue', 'Average Transaction Amount', 'Generated On'],
            'Value': [
                len(data),
                total_revenue,
                round(total_revenue / len(data), 2) if len(data) > 0 else 0,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    # Get the Excel file content
    buffer.seek(0)
    excel_data = buffer.getvalue()
    buffer.close()
    
    # Create the response
    response = HttpResponse(excel_data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="financial_summary_report.xlsx"'
    return response
