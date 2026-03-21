from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from .models import MediAdmin, Patient, Users, Doctor, Pharmacist, Medicine, Cart,Transaction,OrderItem,Order, Appointment, Prescription, PrescriptionMedicine, LabTest, Notification, Review, Leave, AuditLog, LabReportImage, MedicalCondition, PastOperation
from .forms import PatientRegistrationForm, PharmacistRegistrationForm, PatientProfileUpdateForm, DoctorRegistrationForm, PharmacistProfileUpdateForm, MedicineForm, LeaveForm
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.core.files.storage import default_storage
from ml.predictDisease import run_medical_assistant
from google import genai
import json
import os

# Configure Gemini API
# Get API key from environment 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyColdtbbaTVHH8Meza-n2mdHeOUfbLClvQ")
client = genai.Client(api_key=GEMINI_API_KEY)

def chatbot_response(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            
            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            # Check if API key is set
            if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
                return JsonResponse({
                    "response": "Hello! I'm your Mediwise AI assistant. To enable my medical advice capabilities, please configure the Gemini API key in the backend. How can I help you today?"
                })

            # System instructions for medical context
            prompt = f"""
            You are Mediwise AI, a helpful medical assistant for a patient dashboard. 
            Keep your responses concise, professional, and medical-focused. 
            If asked about specific medical conditions, always advise consulting a professional doctor.
            User: {user_message}
            """
            
            response = client.models.generate_content(
                model="gemini-flash-latest", 
                contents=prompt
            )
            return JsonResponse({"response": response.text})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request method"}, status=405)



# Create your views here.


def log_user_action(user, action, details=None, related_object=None, request=None):
    """Log a user action in the audit log
    
    Args:
        user: Users object
        action: Action type from AuditLog.ACTION_CHOICES
        details: Additional details about the action
        related_object: The related model object (e.g., Prescription, Appointment)
        request: HttpRequest object for IP and user agent
    """
    try:
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        related_object_id = None
        related_object_type = None
        
        if related_object:
            related_object_id = related_object.id
            related_object_type = related_object.__class__.__name__
        
        AuditLog.objects.create(
            user=user,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            related_object_id=related_object_id,
            related_object_type=related_object_type
        )
    except Exception as e:
        # Don't let logging errors break the application
        print(f"Error logging action: {e}")


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def update_user_last_login(user):
    """Update the last_login timestamp for a user"""
    try:
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
    except Exception as e:
        print(f"Error updating last login: {e}")


def index(request):
    return render(request, 'index.html')

def contact_us(request):
    """Handle contact form submission"""
    from django.http import JsonResponse
    from django.core.mail import send_mail
    from django.conf import settings
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        # Get form data
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        # Validate required fields
        if not all([name, email, subject, message]):
            return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
        
        # Validate email format
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return JsonResponse({'success': False, 'error': 'Invalid email address'}, status=400)
        
        # Check if AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Prepare email content
        email_subject = f"Contact Form: {subject}"
        email_message = f"""
Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}
        """
        
        # Try to send email
        try:
            send_mail(
                email_subject,
                email_message,
                settings.DEFAULT_FROM_EMAIL,
                ['support@mediwise.com'],  # Replace with your support email
                fail_silently=False,
            )
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you for contacting us! We will respond within 24 hours.',
                    'email_link': 'mailto:support@mediwise.com'
                })
            else:
                from django.contrib import messages
                messages.success(request, 'Your message has been sent successfully. We will respond within 24 hours.')
                return redirect('index')
                
        except Exception as email_error:
            # If email fails, still return success but log the error
            print(f"Email sending failed: {str(email_error)}")
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you for your message. However, our email system is temporarily unavailable. Please contact us directly at support@mediwise.com',
                    'email_link': 'mailto:support@mediwise.com'
                })
            else:
                from django.contrib import messages
                messages.warning(request, 'Your message has been received, but our email system is temporarily unavailable. Please contact us directly at support@mediwise.com')
                return redirect('index')
                
    except Exception as e:
        print(f"Contact form error: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Unable to process your request. Please try again later or email us at support@mediwise.com',
                'email_link': 'mailto:support@mediwise.com'
            }, status=500)
        else:
            from django.contrib import messages
            messages.error(request, 'An error occurred. Please try again later.')
            return redirect('index')

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
            print(f"Checking {role} with user {user}")
            return role, user # Return the object too so you can use it
    return None, None

def login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        role, user_obj = getUser(email, password)
        
        if role == 'admin':
            request.session['admin_id'] = user_obj.id
            # Create user object for audit logging
            try:
                user_model = Users.objects.get(id=user_obj.id, role='admin')
                update_user_last_login(user_model)
                log_user_action(user_model, 'login', 'Admin logged in', request=request)
            except Users.DoesNotExist:
                # Admin user doesn't have a corresponding Users record, create one if needed
                pass
            return redirect('admin_dashboard')
        elif role == 'patient':
            request.session['patient_id'] = user_obj.id
            try:
                user_model = user_obj.user  # Get the Users object from the patient model
                update_user_last_login(user_model)
                log_user_action(user_model, 'login', 'Patient logged in', request=request)
            except AttributeError:
                # Patient doesn't have a corresponding Users record
                pass
            return redirect('patient_dashboard')
        elif role == 'pharmacist':
            request.session['pharmacist_id'] = user_obj.id
            # Create user object for audit logging
            try:
                user_model = user_obj.user  # Get the Users object from the pharmacist model
                update_user_last_login(user_model)
                log_user_action(user_model, 'login', 'Pharmacist logged in', request=request)
            except AttributeError:
                # Pharmacist doesn't have a corresponding Users record
                pass
            return redirect('pharmacist_dashboard')
        elif role == 'doctor':
            # Check registration status for doctors
            if user_obj.registration_status == 'pending':
                return render(request, 'login.html', {'error': 'Your account is pending admin approval.'})
            elif user_obj.registration_status == 'rejected':
                return render(request, 'login.html', {'error': 'Your registration request has been rejected. Please contact support.'})
                
            request.session['doctor_id'] = user_obj.id
            # Create user object for audit logging
            try:
                user_model = user_obj.user  # Get the Users object from the doctor model
                update_user_last_login(user_model)
                log_user_action(user_model, 'login', 'Doctor logged in', request=request)
            except AttributeError:
                # Doctor doesn't have a corresponding Users record
                pass
            return redirect('doctor_dashboard')
        
        return render(request, 'login.html', {'error': 'Invalid credentials'})
         
    return render(request, 'login.html')



def logout(request):
    # Log logout action before flushing session
    user_id = None
    user_role = None
    
    # Determine which user is logging out
    if request.session.get('admin_id'):
        user_id = request.session.get('admin_id')
        user_role = 'admin'
    elif request.session.get('doctor_id'):
        user_id = request.session.get('doctor_id')
        user_role = 'doctor'
    elif request.session.get('pharmacist_id'):
        user_id = request.session.get('pharmacist_id')
        user_role = 'pharmacist'
    elif request.session.get('patient_id'):
        user_id = request.session.get('patient_id')
        user_role = 'patient'
    
    if user_id and user_role:
        try:
            if user_role == 'admin':
                user_model = Users.objects.get(id=user_id, role=user_role)
            elif user_role == 'patient':
                patient = Patient.objects.get(id=user_id)
                user_model = patient.user
            elif user_role == 'pharmacist':
                pharmacist = Pharmacist.objects.get(id=user_id)
                user_model = pharmacist.user
            elif user_role == 'doctor':
                doctor = Doctor.objects.get(id=user_id)
                user_model = doctor.user
            log_user_action(user_model, 'logout', f'{user_role.capitalize()} logged out', request=request)
        except (Users.DoesNotExist, Patient.DoesNotExist, Pharmacist.DoesNotExist, Doctor.DoesNotExist):
            pass  # User not found, proceed with logout
    
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
    #total_long_term_orders = OrderItem.objects.filter(course_duration__isnull=False).count()
    
    # Get orders that have been reordered (refilled)
    # This is a simplified approach - in a real scenario, you'd need to check if the same medicine was ordered again
    #refilled_orders = OrderItem.objects.filter(course_duration__isnull=False, reminder_sent_at__isnull=False).count()
    
    #if total_long_term_orders > 0:
    #    refill_percentage = (refilled_orders / total_long_term_orders) * 100
    #else:
    #    refill_percentage = 0
    
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
        'recent_activities': recent_activities,
    }
    
    return render(request, 'admin/dashboard.html', context)

def patient_dashboard(request):
    from datetime import timedelta
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    
    user = Patient.objects.filter(id=user_id).first()
    
    # Check for incomplete profile
    required_fields = [user.phone_number, user.address, user.date_of_birth, user.blood_group, user.height, user.weight]
    profile_incomplete = any(field in [None, '', 'None'] for field in required_fields)

    # Basic Data Fetching
    pharmacists = Pharmacist.objects.all()
    
    # Get upcoming scheduled appointments
    appointments = Appointment.objects.filter(
        patient=user,
        appointment_date__gte=timezone.now().date(),
        status__in=['scheduled']
    ).prefetch_related('reviews').order_by('appointment_date', 'appointment_time')
    
    # Get all prescriptions with their medicines
    prescriptions = Prescription.objects.filter(patient=user).select_related(
        'doctor', 'appointment'
    ).prefetch_related('medicines').order_by('-created_at')
            
    # Process prescriptions into a flat list for the dashboard
    active_prescriptions = []
    for prescription in prescriptions:
        medicines = prescription.medicines.all()
        for medicine in medicines:
            active_prescriptions.append({
                'prescription': prescription,
                'drug_name': medicine.drug_name_generic,
                'strength': medicine.strength,
                'doctor': prescription.doctor,
                'prescribed_date': prescription.created_at.date(),
                'instructions': medicine.instructions
            })
        
    # Limit to the 3 most recent medicine entries
    active_prescriptions = active_prescriptions[:3]
    
    # Handle Notifications: Mark unread as read
    unread_notifications = Notification.objects.filter(patient=user, is_read=False)
    if unread_notifications.exists():
        unread_notifications.update(is_read=True, read_at=timezone.now())
    
    # Get all notifications for this patient, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=user
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')
    
    # Sidebar/Stat data
    recent_orders = Order.objects.filter(patient=user).order_by('-created_at')[:5]
    cart_count = Cart.objects.filter(patient=user).count()
    
    # Calculate Health Score based on appointments and medicine orders
    from django.db.models import Count
    
    # Count total appointments
    total_appointments = Appointment.objects.filter(patient=user).count()
    
    # Count total medicine orders (from OrderItem)
    total_medicine_orders = OrderItem.objects.filter(
        order__patient=user
    ).aggregate(total=Count('id'))['total'] or 0
    
    # Calculate health score (max 100)
    # Appointments contribute 50% (max 50 points)
    # Medicine orders contribute 50% (max 50 points)
    appointment_points = min(total_appointments * 10, 50)  # 10 points per appointment, max 50
    medicine_points = min(total_medicine_orders * 5, 50)   # 5 points per medicine order, max 50
    health_score = appointment_points + medicine_points
    
    # Determine health progress message based on score
    if health_score >= 80:
        health_progress_message = "Excellent! You're actively managing your health."
    elif health_score >= 60:
        health_progress_message = "Good progress! Keep up with your health routine."
    elif health_score >= 40:
        health_progress_message = "Fair score. Consider more regular check-ups."
    elif health_score >= 20:
        health_progress_message = "Needs improvement. Schedule more appointments."
    else:
        health_progress_message = "Your health metrics need attention. Book an appointment today!"
    
    context = {
        'user': user,
        'profile_incomplete': profile_incomplete,
        'pharmacists': pharmacists,
        'appointments': appointments,
        'active_prescriptions': active_prescriptions,
        'recent_orders': recent_orders,
        'notifications': notifications,
        'cart_count': cart_count,
        'health_score': health_score,
        'health_progress_message': health_progress_message,
    }
    return render(request, 'patient/dashboard.html', context)
def registered_pharmacies(request):
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    
    user = Patient.objects.filter(id=user_id).first()
    
    # Initialize filter variables
    selected_formulation = request.GET.get('formulation', '')
    medicine_search = request.GET.get('search', '')
    
    # Handle prescription_id parameter to search for medicines from prescription
    prescription_id = request.GET.get('prescription_id')
    prescription_medicine_names = set()
    current_search_index = 0
    
    if prescription_id:
        from .models import Prescription, PrescriptionMedicine
        try:
            prescription = Prescription.objects.get(id=prescription_id, patient=user)
            # Get all medicines from this prescription
            prescription_medicines = PrescriptionMedicine.objects.filter(prescription=prescription)
            
            # Extract generic names from prescription medicines
            for prescription_medicine in prescription_medicines:
                if prescription_medicine.drug_name_generic:
                    prescription_medicine_names.add(prescription_medicine.drug_name_generic.lower())
            
            # Convert to list for indexing
            prescription_medicine_names_list = list(prescription_medicine_names)
            
            # Handle navigation through prescription medicines
            if request.GET.get('next_medicine') and prescription_medicine_names_list:
                # Get current search term from session or default to first
                current_search = request.GET.get('search', prescription_medicine_names_list[0])
                try:
                    current_index = prescription_medicine_names_list.index(current_search.lower())
                    next_index = (current_index + 1) % len(prescription_medicine_names_list)
                    medicine_search = prescription_medicine_names_list[next_index]
                except (ValueError, IndexError):
                    medicine_search = prescription_medicine_names_list[0] if prescription_medicine_names_list else ''
            elif request.GET.get('prev_medicine') and prescription_medicine_names_list:
                # Get current search term from session or default to first
                current_search = request.GET.get('search', prescription_medicine_names_list[0])
                try:
                    current_index = prescription_medicine_names_list.index(current_search.lower())
                    prev_index = (current_index - 1) % len(prescription_medicine_names_list)
                    medicine_search = prescription_medicine_names_list[prev_index]
                except (ValueError, IndexError):
                    medicine_search = prescription_medicine_names_list[0] if prescription_medicine_names_list else ''
            elif prescription_medicine_names_list:
                # Default to first medicine name
                medicine_search = prescription_medicine_names_list[0]
                    
        except Prescription.DoesNotExist:
            messages.error(request, "Prescription not found.")
    
    # Get all pharmacists
    pharmacists = Pharmacist.objects.all()
    
    # Get unique formulations from all pharmacies for the filter dropdown
    from django.utils import timezone
    all_formulations = Medicine.objects.filter(
        expiry_date__gt=timezone.now().date()
    ).values_list('formulation', flat=True).distinct().order_by('formulation')
    
    # If a formulation is selected OR medicine search is provided, get medicines for each pharmacy
    if selected_formulation or medicine_search:
        pharmacies_with_medicines = []
        for pharmacist in pharmacists:
            # Build filter conditions
            filter_kwargs = {
                'pharmacist': pharmacist,
                'expiry_date__gt': timezone.now().date()
            }
            
            # Add formulation filter if selected
            if selected_formulation:
                filter_kwargs['formulation__iexact'] = selected_formulation
            
            # Add medicine search filter if provided - search by generic name from prescription
            if medicine_search:
                # Search for medicines matching the prescription's generic names across ALL pharmacies
                # Include both Rx and OTC medicines
                medicines = Medicine.objects.filter(
                    pharmacist=pharmacist,
                    expiry_date__gt=timezone.now().date()
                ).filter(
                    Q(generic_name__icontains=medicine_search) |
                    Q(brand_name__icontains=medicine_search)
                )
                
                # Only include pharmacies that have matching medicines
                if medicines.exists():
                    pharmacies_with_medicines.append({
                        'pharmacist': pharmacist,
                        'medicines': medicines,
                        'medicine_count': medicines.count()
                    })
        pharmacies_data = pharmacies_with_medicines
    else:
        # No filter, show all pharmacies without medicines
        pharmacies_data = [{'pharmacist': pharmacist, 'medicines': [], 'medicine_count': 0} for pharmacist in pharmacists]
    
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
    ).order_by('-created_at')
    
    return render(request, 'patient/pharmacies.html', {
        'user': user,
        'pharmacies_data': pharmacies_data,
        'pharmacists': pharmacists,  # Keep for backward compatibility
        'notifications': notifications,
        'cart_count': cart_count,
        'selected_formulation': selected_formulation,
        'all_formulations': all_formulations,
        'prescription_id': prescription_id,
        'prescription_medicine_names': list(prescription_medicine_names),
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
    
    # Get medicines for this pharmacist, excluding expired ones
    from django.utils import timezone
    medicines = Medicine.objects.filter(
        pharmacist=pharmacist,
        expiry_date__gt=timezone.now().date()  # Only medicines with future expiry dates
    )
    
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
    
    # Support general search in both modes (prescription and regular)
    search_term = request.GET.get('search', '')
    if search_term:
        from django.db.models import Q
        medicines = medicines.filter(
            Q(generic_name__icontains=search_term) |
            Q(brand_name__icontains=search_term) |
            Q(strength__icontains=search_term)
        ).distinct()
    
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
        'unavailable_prescription_medicines': unavailable_prescription_medicines,
        'specific_prescription_id': request.GET.get('prescription_id')
    })


def prescription_medicines_all_pharmacies(request):
    """
    Show all prescription medicines and which pharmacies have them.
    When searching from a prescription, display medicines (by generic name)
    and show all pharmacies where each medicine is available.
    Can show medicines from a specific prescription or all prescriptions.
    """
    user_id = request.session.get('patient_id')
    if user_id is None:
        return redirect('login')
    
    user = Patient.objects.filter(id=user_id).first()
    
    from .models import Prescription, PrescriptionMedicine
    from django.utils import timezone
    from django.db.models import Q
    
    # Get prescription ID (optional - if not provided, show all prescription medicines)
    prescription_id = request.GET.get('prescription_id')
    
    if prescription_id:
        # Show medicines from a specific prescription
        try:
            prescription = Prescription.objects.get(id=prescription_id, patient=user)
            # Get all medicines from this prescription
            prescription_medicines = PrescriptionMedicine.objects.filter(prescription=prescription)
        except Prescription.DoesNotExist:
            messages.error(request, "Prescription not found.")
            return redirect('patient_prescriptions')
    else:
        # Show medicines from ALL prescriptions
        prescription = None
        # Get all prescription medicines for this patient
        prescription_medicines = PrescriptionMedicine.objects.filter(
            prescription__patient=user
        ).select_related('prescription')
    
    # Build list of unique medicine search criteria (name + strength)
    search_criteria = []
    seen_criteria = set()
    
    for pm in prescription_medicines:
        generic_name = pm.drug_name_generic.strip() if pm.drug_name_generic else None
        brand_name = pm.drug_name_brand.strip() if pm.drug_name_brand else None
        strength = pm.strength.strip() if pm.strength else None
        
        # Use generic name if available, otherwise brand name
        name_to_use = generic_name if generic_name else brand_name
        if not name_to_use:
            continue
            
        criteria_key = (name_to_use.lower(), strength.lower() if strength else None)
        if criteria_key not in seen_criteria:
            seen_criteria.add(criteria_key)
            search_criteria.append({
                'name': name_to_use,
                'strength': strength,
                'dosage_frequency': pm.dosage_frequency,
                'instructions': pm.instructions
            })
    
    # Search for these medicines across ALL pharmacies
    medicines_with_pharmacies = []
    
    for criteria in search_criteria:
        med_name = criteria['name']
        prescribed_strength = criteria['strength']
        
        # Build query for name matching
        name_query = Q(generic_name__icontains=med_name) | Q(brand_name__icontains=med_name)
        
        # Base results matching name and not expired
        matching_medicines = Medicine.objects.filter(
            expiry_date__gt=timezone.now().date()
        ).filter(name_query)
        
        # Apply strength filter if prescribed
        if prescribed_strength:
            matching_medicines = matching_medicines.filter(strength__icontains=prescribed_strength)
            
        matching_medicines = matching_medicines.select_related('pharmacist').order_by('generic_name', 'brand_name')
        
        # Group by unique medicine (generic + brand + pharmacist combination)
        medicine_pharmacy_map = {}
        for med in matching_medicines:
            med_key = f"{med.generic_name.lower()}_{med.brand_name.lower()}_{med.pharmacist.id}"
            
            if med_key not in medicine_pharmacy_map:
                medicine_pharmacy_map[med_key] = {
                    'medicine': med,
                    'pharmacies': []
                }
            
            medicine_pharmacy_map[med_key]['pharmacies'].append({
                'pharmacist': med.pharmacist,
                'quantity': med.quantity,
                'price': med.price,
                'strength': med.strength,
                'formulation': med.formulation,
                'medicine_id': med.id
            })
        
        # Create medicine entry with all pharmacies
        if medicine_pharmacy_map:
            for med_key, data in medicine_pharmacy_map.items():
                medicines_with_pharmacies.append({
                    'generic_name': data['medicine'].generic_name,
                    'brand_name': data['medicine'].brand_name,
                    'prescription_dosage_frequency': criteria['dosage_frequency'],
                    'prescription_instructions': criteria['instructions'],
                    'prescription_strength': prescribed_strength,
                    'pharmacies': data['pharmacies']
                })
    
    # Get cart count
    cart_count = Cart.objects.filter(patient=user).count() if user else 0
    
    return render(request, 'patient/prescription_medicines_all_pharmacies.html', {
        'user': user,
        'prescription': prescription,  # Can be None if showing all prescriptions
        'medicines_with_pharmacies': medicines_with_pharmacies,
        'cart_count': cart_count,
    })

def add_to_cart(request, medicine_id):
    if request.method != 'POST':
        return redirect('pharmacy_medicines', pk=1)
    
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=patient_id)
    medicine = Medicine.objects.get(id=medicine_id)
    
    # Check if medicine is expired
    from django.utils import timezone
    if medicine.expiry_date <= timezone.now().date():
        messages.error(request, f"Cannot add {medicine.brand_name} to cart - medicine has expired.")
        return redirect('pharmacy_medicines', pk=medicine.pharmacist.id)
    
    # Check if medicine is Rx (requires prescription)
    prescription_id = request.POST.get('prescription_id')
    is_from_prescription = False
    if prescription_id and prescription_id != 'None':
        # Verify if this prescription actually contains this medicine
        try:
            from .models import Prescription, PrescriptionMedicine
            # Use flexible matching as in checkout
            rx_medicine_name = medicine.generic_name.lower().strip()
            pm_exists = PrescriptionMedicine.objects.filter(
                prescription_id=prescription_id,
                prescription__patient=patient
            ).filter(
                Q(drug_name_generic__icontains=rx_medicine_name) | 
                Q(drug_name_brand__icontains=rx_medicine_name)
            ).exists()
            
            if pm_exists:
                is_from_prescription = True
        except (ValueError, Prescription.DoesNotExist):
            pass

    if medicine.medicine_type == 'Rx':
        # Check if the medicine is already in the cart
        existing_cart_item = Cart.objects.filter(patient=patient, medicine=medicine).first()
        
        if existing_cart_item:
            # If item already exists, update its quantity
            cart_item = existing_cart_item
            cart_item.quantity = 5
            if float(medicine.price) < 20:
                cart_item.quantity = max(cart_item.quantity, 5)
        else:
            # If new item, create it with appropriate quantity
            quantity_to_set = 5
            if float(medicine.price) < 20:
                quantity_to_set = max(quantity_to_set, 5)
            cart_item = Cart.objects.create(patient=patient, medicine=medicine, quantity=quantity_to_set, requires_prescription=True)
        
        cart_item.requires_prescription = True
        if is_from_prescription:
            cart_item.added_from_prescription = True
        cart_item.save()
        
        if is_from_prescription:
            messages.success(request, f"{medicine.brand_name} added from your prescription.")
        else:
            messages.warning(request, f"{medicine.brand_name} is a prescription-only medicine. You will need to upload a prescription before checkout.")
        return redirect('view_cart')
    
    # For OTC medicines, proceed normally
    if medicine.quantity > 0:
        # Check if the medicine is already in the cart
        existing_cart_item = Cart.objects.filter(patient=patient, medicine=medicine).first()
        
        if existing_cart_item:
            # If item already exists, update its quantity
            cart_item = existing_cart_item
            cart_item.quantity = 5
            if float(medicine.price) < 20:
                cart_item.quantity = max(cart_item.quantity, 5)
        else:
            # If new item, create it with appropriate quantity
            quantity_to_set = 5
            if float(medicine.price) < 20:
                quantity_to_set = max(quantity_to_set, 5)
            cart_item = Cart.objects.create(patient=patient, medicine=medicine, quantity=quantity_to_set)
        
        cart_item.save()
        messages.success(request, f"{medicine.brand_name} added to cart.")
        return redirect('view_cart')
    else:
        messages.error(request, "Medicine out of stock.")
        return redirect('pharmacy_medicines', pk=medicine.pharmacist.id)

def view_cart(request):
    from datetime import timedelta
    from decimal import Decimal
    from django.utils import timezone
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    patient = Patient.objects.get(id=patient_id)
    # Get cart items and filter out any that reference expired medicines
    cart_items = Cart.objects.filter(patient=patient).select_related('medicine', 'medicine__pharmacist')
    
    # Remove cart items that reference expired medicines
    expired_cart_items = []
    valid_cart_items = []
    
    for item in cart_items:
        if item.medicine.expiry_date <= timezone.now().date():
            expired_cart_items.append(item)
        else:
            valid_cart_items.append(item)
    
    # Remove expired items from cart
    if expired_cart_items:
        for item in expired_cart_items:
            item.delete()
        messages.warning(request, f"Removed {len(expired_cart_items)} expired medicine(s) from your cart.")
        
    cart_items = valid_cart_items
    
    # Calculate subtotal
    subtotal = 0
    for item in cart_items:
        subtotal += item.medicine.price * item.quantity
    
    # Calculate GST (18%)
    gst_rate = Decimal('0.18')
    gst_amount = round(subtotal * gst_rate, 2)
    total_amount = subtotal + gst_amount
    
    # Get cart count for the cart icon
    cart_count = len(cart_items) if patient else 0

    unread_notifications = Notification.objects.filter(patient=patient, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()

    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        patient=patient
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')
    
    
    return render(request, 'patient/cart.html', {
        'user': patient,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'gst_amount': gst_amount,
        'total_amount': total_amount,
        'cart_count': cart_count,
        'notifications': notifications
    })

def update_cart_quantity(request, item_id, action):
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    cart_item = Cart.objects.filter(id=item_id, patient_id=patient_id).first()
    if not cart_item:
        return redirect('view_cart')
    
    # Determine if this medicine should have a minimum quantity of 5
    min_quantity = 5 if float(cart_item.medicine.price) < 20 else 1
    
    if action == 'increase':
        if cart_item.quantity < cart_item.medicine.quantity:
            cart_item.quantity += 1
            cart_item.save()
        else:
            messages.warning(request, "Cannot exceed available stock.")
    elif action == 'decrease':
        if cart_item.quantity > min_quantity:
            cart_item.quantity -= 1
            cart_item.save()
        elif cart_item.quantity == min_quantity:
            messages.warning(request, "Minimum quantity is 5.")
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
    rx_items = cart_items.filter(requires_prescription=True, added_from_prescription=False)
    if rx_items.exists():
        first_rx_item = rx_items.first()
        messages.error(request, f"Prescription required for {first_rx_item.medicine.generic_name}. Please add this medicine from a valid prescription before proceeding to checkout.")
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
    
    # Store order details in session for payment processing
    request.session['pending_order'] = {
        'subtotal': float(subtotal),
        'gst_amount': float(gst_amount),
        'total_amount': float(total_amount),
        'cart_items': [{'id': item.id, 'quantity': item.quantity, 'medicine_id': item.medicine.id, 'price': float(item.medicine.price)} for item in cart_items]
    }
    
    # Redirect to payment portal
    return redirect('payment_portal')

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
    from .models import Notification, LabReportImage
    
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
    ).order_by('-created_at')
    
    # Get lab report images for this patient
    lab_reports = LabReportImage.objects.filter(patient=user).order_by('-uploaded_at')
    
    return render(request, 'patient/records.html', {
        'user': user, 
        'notifications': notifications,
        'cart_count': cart_count,
        'lab_reports': lab_reports
    })


def upload_lab_report(request):
    if request.method == 'POST':
        user_id = request.session.get('patient_id')
        if user_id is None:
            return redirect('login')
        
        user = Patient.objects.filter(id=user_id).first()
        if not user:
            return redirect('login')
        
        if 'lab_report_image' in request.FILES:
            lab_report_image = request.FILES['lab_report_image']
            report_name = request.POST.get('report_name', f'Lab Report {timezone.now().strftime("%Y-%m-%d")}')
            notes = request.POST.get('notes', '')
            
            # Validate file type
            import os
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf']
            ext = os.path.splitext(lab_report_image.name)[1].lower()
            if ext not in allowed_extensions:
                messages.error(request, 'Invalid file type. Please upload an image file (JPG, PNG, GIF, BMP) or PDF.')
                return redirect('patient_records')
            
            # Create LabReportImage instance
            lab_report = LabReportImage.objects.create(
                patient=user,
                image=lab_report_image,
                report_name=report_name,
                notes=notes
            )
            
            messages.success(request, 'Lab report uploaded successfully!')
        else:
            messages.error(request, 'No file selected. Please choose an image or PDF file.')
        
        return redirect('patient_records')
    
    return redirect('patient_records')


def delete_lab_report(request, report_id):
    if request.method == 'POST':
        user_id = request.session.get('patient_id')
        if user_id is None:
            return redirect('login')
        
        user = Patient.objects.filter(id=user_id).first()
        if not user:
            return redirect('login')
        
        try:
            lab_report = LabReportImage.objects.get(id=report_id, patient=user)
            # Store the file name before deleting the model instance
            file_to_delete = lab_report.image.name
            lab_report.delete()
            
            # Delete the physical file from storage
            if file_to_delete and default_storage.exists(file_to_delete):
                default_storage.delete(file_to_delete)
                
            messages.success(request, 'Lab report and associated file deleted successfully!')
        except LabReportImage.DoesNotExist:
            messages.error(request, 'Lab report not found or you do not have permission to delete it.')
        
        return redirect('patient_records')
    
    return redirect('patient_records')


import time
import logging

logger = logging.getLogger(__name__)

def predict_disease(request, report_id):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    user_id = request.session.get('patient_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    start_time = time.time()
    logger.info(f"Starting prediction for report_id: {report_id}, user_id: {user_id}")
    
    try:
        # 1. Fetch the report and verify ownership
        lab_report = LabReportImage.objects.get(id=report_id, patient_id=user_id)
        file_path = lab_report.image.path # Absolute path to the file
        logger.info(f"File path: {file_path}")

        # 2. Call the ML function directly
        result = run_medical_assistant(file_path)
        processing_time = time.time() - start_time
        logger.info(f"Prediction completed in {processing_time:.2f} seconds")

        # 3. Handle errors returned by the ML logic
        if "error" in result:
            logger.error(f"Prediction error: {result['error']}")
            return JsonResponse({
                'success': False, 
                'error': result['error']
            }, status=400)

        # 4. Success Response
        response_data = {
            'success': True,
            'result': result,
            'message': 'Disease prediction completed successfully!',
            'processing_time': f"{processing_time:.2f} seconds"
        }
        logger.info(f"Prediction successful: {result.get('condition', 'Unknown')}")
        return JsonResponse(response_data)

    except LabReportImage.DoesNotExist:
        logger.error(f"Report not found: {report_id}")
        return JsonResponse({'success': False, 'error': 'Report not found'}, status=404)
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Prediction failed after {processing_time:.2f} seconds: {str(e)}")
        return JsonResponse({'success': False, 'error': f'System error: {str(e)}'}, status=500)

def parse_prediction_output(output):
    """
    Parse the output from the prediction function to extract relevant information
    """
    import re
    
    # Check if the output contains the custom "no data" message
    if "Unable to determine - No readable data found" in output:
        return {
            'condition': "Unable to determine - No readable data found",
            'confidence': "0",
            'diet': "Unable to provide recommendations based on this image",
            'workout': "Unable to provide recommendations based on this image",
            'precautions': "Please ensure the image is clear and contains readable lab report data"
        }
    
    # Extract predicted condition
    condition_match = re.search(r'Predicted Condition: (.+)', output)
    condition = condition_match.group(1).strip() if condition_match else "Unknown"
    
    # Extract confidence
    confidence_match = re.search(r'Model Confidence: ([\d.]+)%', output)
    confidence = confidence_match.group(1).strip() if confidence_match else "0.0"
    
    # Extract diet recommendation
    diet_match = re.search(r'Diet: (.+)', output)
    diet = diet_match.group(1).strip() if diet_match else "No specific recommendations"
    
    # Extract workout recommendation
    workout_match = re.search(r'Workout: (.+)', output)
    workout = workout_match.group(1).strip() if workout_match else "No specific recommendations"
    
    # Extract precautions
    precautions_match = re.search(r'Precautions: (.+)', output)
    precautions = precautions_match.group(1).strip() if precautions_match else "No specific precautions"
    
    return {
        'condition': condition,
        'confidence': confidence,
        'diet': diet,
        'workout': workout,
        'precautions': precautions
    }

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
    ).order_by('-created_at')
    
    # Get cart count for the cart icon
    cart_count = Cart.objects.filter(patient=patient).count() if patient else 0
    
    return render(request, 'patient/orders.html', {
        'user': patient,
        'orders': orders,
        'notifications': notifications,
        'cart_count': cart_count
    })

def order_details_ajax(request, order_id):
    """AJAX view to return order details for the modal"""
    from django.http import JsonResponse
    
    try:
        order = Order.objects.prefetch_related(
            'items__medicine__pharmacist', 
            'transaction', 
            'reviews'
        ).get(id=order_id)
        
        # Add unique pharmacists for the order
        pharmacists_set = set()
        for item in order.items.all():
            if item.medicine.pharmacist:
                pharmacists_set.add(item.medicine.pharmacist)
        order.unique_pharmacists = list(pharmacists_set)
        
        # Get the review for this order if it exists
        order_review = None
        if hasattr(order, 'reviews') and order.reviews.exists():
            order_review = order.reviews.first()
        
        context = {
            'order': order,
            'order_review': order_review,
            'is_completed': order.status == 'completed'
        }
        
        return render(request, 'patient/order_details_modal.html', context)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)


def submit_order_review(request, order_id):
    """Handle order review submission"""
    from django.contrib import messages
    
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=patient_id)
        order = Order.objects.get(id=order_id, patient=patient)
        
        # Only allow reviews for completed orders
        if order.status != 'completed':
            messages.error(request, "You can only review completed orders.")
            return redirect('patient_orders')
        
        # Check if review already exists
        existing_review = Review.objects.filter(patient=patient, order=order).first()
        if existing_review:
            messages.info(request, "You have already reviewed this order.")
            return redirect('patient_orders')
        
        if request.method == 'POST':
            rating = request.POST.get('rating')
            review_text = request.POST.get('review_text', '').strip()
            
            if not rating:
                messages.error(request, "Please select a rating.")
                return redirect('patient_orders')
            
            # Create the review
            Review.objects.create(
                patient=patient,
                review_type='order',
                order=order,
                rating=int(rating),
                review_text=review_text if review_text else None
            )
            
            messages.success(request, "Thank you for your review!")
        
        return redirect('patient_orders')
        
    except Patient.DoesNotExist:
        return redirect('login')
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('patient_orders')


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
    ).order_by('-created_at')
    
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
    """Check availability of medicines in specified pharmacy or all pharmacies, excluding expired medicines.
    Returns detailed information about which pharmacies have which medicines."""
    from .models import Medicine
    from decimal import Decimal
    from django.utils import timezone
    from collections import defaultdict
    
    # If specific pharmacy is specified, check only that pharmacy
    if pharmacist:
        pharmacy_medicines = Medicine.objects.filter(
            pharmacist=pharmacist,
            expiry_date__gt=timezone.now().date()  # Only non-expired medicines
        )
        pharmacy_list = [pharmacist]
    else:
        # Check all pharmacies, excluding expired medicines
        pharmacy_medicines = Medicine.objects.filter(
            expiry_date__gt=timezone.now().date()  # Only non-expired medicines
        ).select_related('pharmacist')
        pharmacy_list = Pharmacist.objects.all()
    
    # Build a comprehensive medicine dictionary
    # Structure: {medicine_name: [{pharmacy_info}, ...]}
    medicine_dict = {}
    for med in pharmacy_medicines:
        key = med.generic_name.lower().strip()
        if key not in medicine_dict:
            medicine_dict[key] = []
        
        medicine_dict[key].append({
            'medicine': med,
            'stock': med.quantity,
            'price': str(med.price),
            'pharmacy_id': med.pharmacist.id,
            'pharmacy_name': med.pharmacist.pharmacy_name
        })
    
    # Track pharmacy inventory for aggregation
    pharmacy_inventory = defaultdict(lambda: {
        'medicines': [],
        'total_items': 0,
        'total_price': Decimal('0'),
        'has_all_medicines': False
    })
    
    available_medicines = []
    unavailable_medicines = []
    medicine_to_pharmacies = {}  # Map each medicine to its available pharmacies
    
    # Process each medicine from the prescription
    for medicine in extracted_medicines:
        med_name = medicine['name'].lower().strip()
        medicine_key = medicine['name']  # Original case for display
        
        if med_name in medicine_dict:
            # Find all pharmacies with this medicine in stock
            matching_pharmacies = []
            for pharmacy_med in medicine_dict[med_name]:
                if pharmacy_med['stock'] > 0:
                    matching_pharmacies.append(pharmacy_med)
                    
                    # Add to available medicines list
                    available_medicines.append({
                        'name': pharmacy_med['medicine'].generic_name,
                        'brand': pharmacy_med['medicine'].brand_name,
                        'strength': pharmacy_med['medicine'].strength,
                        'stock': pharmacy_med['stock'],
                        'price': pharmacy_med['price'],
                        'pharmacy_id': pharmacy_med['pharmacy_id'],
                        'pharmacy_name': pharmacy_med['pharmacy_name'],
                        'medicine_id': pharmacy_med['medicine'].id,
                        'extracted_info': medicine
                    })
                    
                    # Update pharmacy inventory tracking
                    pharma_id = pharmacy_med['pharmacy_id']
                    pharmacy_inventory[pharma_id]['medicines'].append(medicine_key)
                    pharmacy_inventory[pharma_id]['total_items'] += 1
                    try:
                        pharmacy_inventory[pharma_id]['total_price'] += Decimal(pharmacy_med['price'])
                    except:
                        pass
            
            medicine_to_pharmacies[medicine_key] = [
                {'pharmacy_id': p['pharmacy_id'], 'pharmacy_name': p['pharmacy_name']}
                for p in matching_pharmacies
            ]
            
            # If no pharmacy has this medicine in stock
            if not matching_pharmacies:
                unavailable_medicines.append({
                    'name': medicine['name'],
                    'reason': 'Out of stock in all pharmacies',
                    'extracted_info': medicine,
                    'available_pharmacies': []
                })
        else:
            unavailable_medicines.append({
                'name': medicine['name'],
                'reason': 'Not available in any pharmacy',
                'extracted_info': medicine,
                'available_pharmacies': []
            })
    
    # Determine which pharmacies have ALL medicines from the prescription
    total_unique_medicines = len(set([m['name'].lower().strip() for m in extracted_medicines]))
    
    for pharma_id, inventory in pharmacy_inventory.items():
        unique_medicines_at_pharmacy = len(set([m.lower().strip() for m in inventory['medicines']]))
        inventory['has_all_medicines'] = (unique_medicines_at_pharmacy == total_unique_medicines)
    
    # Add pharmacy summary information
    pharmacy_summary = []
    for pharma_id, inventory in pharmacy_inventory.items():
        pharmacy_obj = Pharmacist.objects.filter(id=pharma_id).first()
        if pharmacy_obj:
            pharmacy_summary.append({
                'pharmacy_id': pharma_id,
                'pharmacy_name': inventory['medicines'][0] if inventory['medicines'] else '',
                'medicines_available': inventory['medicines'],
                'total_medicines_count': len(inventory['medicines']),
                'has_all_medicines': inventory['has_all_medicines'],
                'estimated_total_price': str(inventory['total_price']),
                'completeness_percentage': round((len(inventory['medicines']) / total_unique_medicines * 100), 1) if total_unique_medicines > 0 else 0
            })
    
    # Sort pharmacies: those with all medicines first, then by completeness percentage
    pharmacy_summary.sort(key=lambda x: (-x['has_all_medicines'], -x['completeness_percentage']))
    
    return available_medicines, unavailable_medicines, pharmacy_summary, medicine_to_pharmacies

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
            available_medicines, unavailable_medicines, pharmacy_summary, medicine_to_pharmacies = check_medicine_availability(extracted_medicines, pharmacist)
            upload.available_medicines = available_medicines
            upload.unavailable_medicines = unavailable_medicines
            upload.pharmacy_summary = pharmacy_summary
            upload.medicine_to_pharmacies = medicine_to_pharmacies
            
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
    
    # Add medicine availability information - SEARCH ACROSS ALL PHARMACIES
    for upload in uploaded_prescriptions:
        # Get extracted medicines
        upload.extracted_medicines = upload.extracted_medicines or []
        
        # Check availability across ALL pharmacies (pass None to search all)
        available_medicines, unavailable_medicines, pharmacy_summary, medicine_to_pharmacies = check_medicine_availability(upload.extracted_medicines, pharmacist=None)
        upload.available_medicines = available_medicines
        upload.unavailable_medicines = unavailable_medicines
        upload.pharmacy_summary = pharmacy_summary
        upload.medicine_to_pharmacies = medicine_to_pharmacies
    
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
        
        # Store file name for deletion
        file_to_delete = prescription.prescription_image.name
        
        # Delete the prescription
        prescription.delete()
        
        # Delete the physical file
        if file_to_delete and default_storage.exists(file_to_delete):
            default_storage.delete(file_to_delete)
            
        messages.success(request, f"Prescription for {pharmacy_name} and its associated file have been successfully deleted.")
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
        prescription = Prescription.objects.select_related('doctor', 'patient', 'appointment').prefetch_related('medicines', 'lab_tests').get(
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
    medicine_header = ['Medicine', 'Strength', 'Dosage', 'Quantity']
    medicine_data = [medicine_header]
    
    # Add medicines data
    for medicine in prescription.medicines.all():
        medicine_row = [
            f"{medicine.drug_name_generic}{(' (' + medicine.drug_name_brand + ')') if medicine.drug_name_brand else ''}",
            medicine.strength,
            medicine.dosage_frequency,
            medicine.total_quantity
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
    
    # Lab Tests Section
    if prescription.lab_tests.exists():
        elements.append(Paragraph("LABORATORY TESTS REQUIRED", header_style))
        elements.append(Spacer(1, 10))
        
        # Lab tests table header
        lab_test_header = ['Test Name', 'Category', 'Priority', 'Instructions']
        lab_test_data = [lab_test_header]
        
        # Add lab tests data
        for lab_test in prescription.lab_tests.all():
            lab_test_row = [
                lab_test.test_name,
                lab_test.get_test_category_display(),
                lab_test.get_priority_display(),
                lab_test.instructions or "N/A"
            ]
            lab_test_data.append(lab_test_row)
        
        # Create lab tests table
        lab_test_table = Table(lab_test_data, colWidths=[50*mm, 30*mm, 20*mm, 70*mm])
        lab_test_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#eff6ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dbeafe')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(lab_test_table)
        elements.append(Spacer(1, 20))
    
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
    ).order_by('-created_at')
    
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
        
        # Convert appointment_date to datetime.date object
        from datetime import datetime
        appointment_date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        
        # Check if doctor is on leave on this date
        from .models import Leave
        leave_exists = Leave.objects.filter(
            doctor=doctor,
            leave_from__lte=appointment_date_obj,
            leave_to__gte=appointment_date_obj
        ).exists()
        
        if leave_exists:
            messages.error(request, f'Sorry, Dr. {doctor.first_name} {doctor.last_name} is on leave on {appointment_date}. Please choose another date.')
            return redirect('book_appointment', doctor_id=doctor_id)
        
        Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason_for_visit=reason
        )
        messages.success(request, f'Appointment booked successfully with Dr. {doctor.first_name} {doctor.last_name} on {appointment_date} at {appointment_time}')
        return redirect('patient_appointments')

    # Get preferred date from query parameters
    preferred_date = request.GET.get('preferred_date')

    
    context = {
        'user': patient,
        'doctor': doctor,
        'cart_count': cart_count,
        'preferred_date': preferred_date
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
    ).order_by('-created_at')
    
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
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    
    context = {
        'pharmacist': pharmacist,
        'data': dashboard_data,
        'pharmacist_notification_count': pharmacist_notification_count
    }
    return render(request, 'pharmacist/dashboard.html', context)

def pharmacist_earnings(request):
    from .models import Pharmacist, OrderItem, Order
    from django.db.models import Sum, Count
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    pharmacist_id = request.session.get('pharmacist_id')
    
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except:
        return redirect('login')
    
    # Get filter parameters
    filter_type = request.GET.get('filter', 'week')  # week, month, year, all
    
    # Calculate date ranges based on filter
    today = timezone.now().date()
    
    if filter_type == 'week':
        start_date = today - timedelta(days=7)
        period_name = 'This Week'
    elif filter_type == 'month':
        start_date = today - timedelta(days=30)
        period_name = 'This Month'
    elif filter_type == 'year':
        start_date = today - timedelta(days=365)
        period_name = 'This Year'
    else:  # all time
        start_date = None
        period_name = 'All Time'
    
    # Build base query for orders (count ALL orders placed)
    orders_query = Order.objects.filter(
        items__medicine__pharmacist=pharmacist
    ).distinct()
    
    # Build base query for successful orders (for earnings calculation)
    successful_orders_query = Order.objects.filter(
        items__medicine__pharmacist=pharmacist,
        status='completed'
    ).distinct()
    
    if start_date:
        orders_query = orders_query.filter(created_at__date__gte=start_date)
        successful_orders_query = successful_orders_query.filter(created_at__date__gte=start_date)
    
    # Calculate total orders (all orders placed)
    total_orders = orders_query.count()
    
    # Calculate successful orders
    successful_orders = successful_orders_query.count()
    
    # Calculate total earnings from successful orders only
    total_earnings = successful_orders_query.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Calculate average order value (based on successful orders)
    avg_order_value = total_earnings / successful_orders if successful_orders > 0 else 0
    
    # Get earnings by day for chart (last 7 days) - only successful orders
    earnings_by_day = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_earnings = Order.objects.filter(
            items__medicine__pharmacist=pharmacist,
            status='completed',
            created_at__date=day
        ).distinct().aggregate(total=Sum('total_amount'))['total'] or 0
        
        earnings_by_day.append({
            'date': day.strftime('%a'),
            'earnings': float(day_earnings),
            'full_date': day.strftime('%Y-%m-%d')
        })
    
    # Get top selling medicines (from successful orders)
    top_medicines = OrderItem.objects.filter(
        order__in=successful_orders_query,
        medicine__pharmacist=pharmacist
    ).values(
        'medicine__brand_name',
        'medicine__generic_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price_at_order')
    ).order_by('-total_revenue')[:5]
    
    # Get recent transactions (from successful orders)
    recent_transactions = OrderItem.objects.filter(
        order__in=successful_orders_query,
        medicine__pharmacist=pharmacist
    ).select_related(
        'order', 'order__patient', 'medicine'
    ).order_by('-order__created_at')[:10]
    
    context = {
        'pharmacist': pharmacist,
        'total_earnings': round(total_earnings, 2),
        'total_orders': total_orders,
        'successful_orders': successful_orders,
        'avg_order_value': round(avg_order_value, 2),
        'period_name': period_name,
        'filter_type': filter_type,
        'earnings_by_day': earnings_by_day,
        'top_medicines': top_medicines,
        'recent_transactions': recent_transactions,
    }
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
    return render(request, 'pharmacist/earnings.html', context)


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
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
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
    
    # Get all medicines for this pharmacist
    all_medicines = Medicine.objects.filter(pharmacist=pharmacist).order_by('-created_at')
    
    # Separate current and expired medicines
    today = timezone.now().date()
    current_medicines = all_medicines.filter(expiry_date__gt=today)
    expired_medicines = all_medicines.filter(expiry_date__lte=today)
    
    # Calculate soon date (10 days from now) for near-expiry highlighting
    soon = today + timedelta(days=10)
    
    context = {
        'pharmacist': pharmacist,
        'current_medicines': current_medicines,
        'expired_medicines': expired_medicines,
        'form': form,
        'today': today,
        'soon': soon
    }
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
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

def delete_medicine(request, pk):
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    medicine = Medicine.objects.filter(id=pk, pharmacist_id=pharmacist_id).first()
    if not medicine:
        messages.error(request, "Medicine not found.")
        return redirect('pharmacist_inventory')
    
    if request.method == 'POST':
        medicine.delete()
        messages.success(request, "Medicine deleted successfully!")
    
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
    successful_orders = orders.filter(status='completed').count()
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
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
    return render(request, 'pharmacist/orders.html', context)

def pharmacist_notifications(request):
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        return redirect('login')
    
    # Mark all unread notifications as read and update their read_at timestamp
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification
    
    unread_notifications = Notification.objects.filter(pharmacist=pharmacist, is_read=False)
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    
    # Get all notifications for this pharmacist, excluding those read more than 2 days ago
    two_days_ago = timezone.now() - timedelta(days=2)
    notifications = Notification.objects.filter(
        pharmacist=pharmacist
    ).filter(
        # Either not read yet, or read within the last 2 days
        Q(is_read=False) | Q(read_at__gte=two_days_ago)
    ).order_by('-created_at')
    
    # Get cart count for the cart icon (for consistency with other views)
    cart_count = Cart.objects.filter(patient__in=Patient.objects.all()).count()
    
    context = {
        'user': pharmacist,
        'notifications': notifications,
        'cart_count': cart_count,
    }
    
    # Get notification count for the pharmacist (already filtered in query above)
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
    return render(request, 'pharmacist/notifications.html', context)

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
            medicine__pharmacist=pharmacist
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
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    
    return render(request, 'pharmacist/customers.html', {
        'user': pharmacist,
        'patient_data': patient_data,
        'cart_count': cart_count,
        'pharmacist_notification_count': pharmacist_notification_count
    })

def pharmacist_customer_details_ajax(request, patient_id):
    """AJAX view to return customer details HTML"""
    from django.http import JsonResponse
    from django.template.loader import render_to_string
    
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
        patient = Patient.objects.get(id=patient_id)
        
        # Get order items for this patient from this pharmacist
        order_items = OrderItem.objects.filter(
            order__patient=patient,
            medicine__pharmacist=pharmacist
        ).select_related('medicine', 'order').order_by('-order__created_at')
        
        # Get unique orders
        orders_dict = {}
        for item in order_items:
            order_id = item.order.id
            if order_id not in orders_dict:
                orders_dict[order_id] = {
                    'order': item.order,
                    'items': [],
                    'total_amount': float(item.order.total_amount),
                    'status': item.order.get_status_display(),
                    'created_at': item.order.created_at
                }
            orders_dict[order_id]['items'].append(item)
        
        orders_list = list(orders_dict.values())
        
        # Calculate total spent with this pharmacist
        total_spent = sum(order['total_amount'] for order in orders_list)
        
        # Render the HTML template
        html_content = render_to_string('pharmacist/customer_details_modal.html', {
            'patient': patient,
            'orders': orders_list,
            'total_spent': total_spent,
            'order_count': len(orders_list)
        })
        
        return JsonResponse({'success': True, 'html': html_content})
        
    except Pharmacist.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Pharmacist not found'})
    except Patient.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Patient not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

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
                order = Order.objects.get(id=order_id, patient=patient, status='completed')
                
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
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        return redirect('login')
    
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
        return redirect('pharmacist_orders')
    
    try:
        import json
        from django.http import JsonResponse
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
        order = Order.objects.get(id=order_id)
        
        # Verify that this order contains medicines from this pharmacist
        pharmacist_medicines = Medicine.objects.filter(pharmacist=pharmacist)
        order_items = OrderItem.objects.filter(order=order, medicine__in=pharmacist_medicines)
        
        if not order_items.exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
            # Only add messages for non-AJAX requests
            messages.error(request, "You don't have permission to update this order.")
            return redirect('pharmacist_orders')
        
        # Update status - handle both JSON and form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            new_status = data.get('status')
        else:
            new_status = request.POST.get('status')
        
        if new_status and new_status in dict(Order.ORDER_STATUS).keys():
            old_status = order.status
            order.status = new_status
            order.save()
            
            # Create notification for the patient about status change
            from .models import Notification
            
            # Map status to user-friendly messages
            status_messages = {
                'pending': 'Your order is being processed',
                'preparing': 'Your order is being prepared',
                'out_for_delivery': 'Your order is out for delivery',
                'completed': 'Your order has been completed',
                'delayed': 'Your order has been delayed',
                'failed': 'Your order could not be fulfilled'
            }
            
            notification_title = status_messages.get(new_status, f'Order status updated')
            notification_message = f'Your order #{order.id} status has been updated to {order.get_status_display()}. Please check your order details for more information.'
            
            Notification.objects.create(
                patient=order.patient,
                notification_type='order_status',
                title=notification_title,
                message=notification_message,
                related_id=order.id
            )
            
            # Track earnings when order becomes completed
            if old_status not in ['completed'] and new_status == 'completed':
                # Calculate earnings for this order
                order_earnings = order.total_amount
                
                # Log the successful order for earnings tracking
                log_user_action(
                    pharmacist.user if hasattr(pharmacist, 'user') else None,
                    'order_completed',
                    f'Order #{order.id} marked as completed. Earnings: ₹{order_earnings}',
                    related_object=order,
                    request=request
                )
                
                success_message = f"Order #{order.id} status updated to {order.get_status_display()}. Earnings of ₹{order_earnings} recorded."
            else:
                success_message = f"Order #{order.id} status updated to {order.get_status_display()}."
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'new_status': order.get_status_display(),
                    'status_code': new_status
                })
            
            # Only add messages for non-AJAX requests
            messages.success(request, success_message)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid status selected'}, status=400)
            # Only add messages for non-AJAX requests
            messages.error(request, "Invalid status selected.")
            
    except (Pharmacist.DoesNotExist, Order.DoesNotExist):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Order not found'}, status=404)
        # Only add messages for non-AJAX requests
        messages.error(request, "Order not found.")
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': f'Error updating order: {str(e)}'}, status=500)
        # Only add messages for non-AJAX requests
        messages.error(request, f"Error updating order: {str(e)}")
    
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
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
    return render(request, 'pharmacist/ratings_feedback.html', context)

def pharmacist_restock(request):
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    pharmacist_id = request.session.get('pharmacist_id')
    if not pharmacist_id:
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        return redirect('login')
    
    # Get medicines with low stock (less than 20)
    low_stock_medicines = Medicine.objects.filter(
        pharmacist=pharmacist,
        quantity__lt=20
    ).order_by('quantity')
    
    # Get medicines near expiry (within 10 days)
    ten_days_from_now = timezone.now().date() + timedelta(days=10)
    expiry_alert_medicines = Medicine.objects.filter(
        pharmacist=pharmacist,
        expiry_date__lte=ten_days_from_now,
        expiry_date__gte=timezone.now().date()
    ).order_by('expiry_date')
    
    # Get cart count for the cart icon
    # Get patient_id from session to check if there's a patient logged in
    patient_id = request.session.get('patient_id')
    if patient_id:
        try:
            patient = Patient.objects.get(id=patient_id)
            cart_count = Cart.objects.filter(patient=patient).count()
        except Patient.DoesNotExist:
            cart_count = 0
    else:
        cart_count = 0
    
    context = {
        'user': pharmacist,
        'low_stock_medicines': low_stock_medicines,
        'expiry_alert_medicines': expiry_alert_medicines,
        'cart_count': cart_count
    }
    
    # Get notification count for the pharmacist
    from .models import Notification
    pharmacist_notification_count = Notification.objects.filter(pharmacist=pharmacist, is_read=False).count()
    context['pharmacist_notification_count'] = pharmacist_notification_count
    
    return render(request, 'pharmacist/restock.html', context)



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
    from datetime import datetime, timedelta, date
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
    
    # Get all leave dates for current month
    from datetime import date
    current_month_leaves = Leave.objects.filter(
        doctor=doctor,
        leave_from__month=current_month,
        leave_from__year=current_year
    ).values('leave_from', 'leave_to')
    
    # Create calendar data
    cal = calendar.monthcalendar(current_year, current_month)
    month_name = calendar.month_name[current_month]
    
    # Prepare appointment days
    appointment_days = set()
    for appt_date in monthly_appointments:
        appointment_days.add(appt_date.day)
    
    # Prepare leave days
    leave_days = set()
    for leave in current_month_leaves:
        leave_from = leave['leave_from']
        leave_to = leave['leave_to']
        
        # Add all days in the leave period
        current_date = leave_from
        while current_date <= leave_to:
            if current_date.month == current_month and current_date.year == current_year:
                leave_days.add(current_date.day)
            current_date = date(current_date.year, current_date.month, current_date.day) + timedelta(days=1)
    
    # Initialize leave form
    leave_form = LeaveForm()
    
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
        'leave_days': leave_days,
        'today': today,
        'leave_form': leave_form,
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
    
    # Get search query if provided
    search_query = request.GET.get('search', '').strip()
    
    # Get only completed appointments for this doctor to show patients with completed appointments
    completed_appointments = Appointment.objects.filter(
        doctor=doctor,
        status='completed'
    ).select_related('patient').prefetch_related('reviews').order_by('-appointment_date')
    
    # Apply search filter if query exists
    if search_query:
        completed_appointments = completed_appointments.filter(
            Q(patient__first_name__icontains=search_query) | 
            Q(patient__last_name__icontains=search_query) |
            Q(patient__email__icontains=search_query)
        )
    
    # Get unique patients from completed appointments (most recent completed appointment for each patient)
    unique_patients = []
    seen_patients = set()
    
    # Get the most recent completed appointment for each patient
    for appointment in completed_appointments:
        if appointment.patient.id not in seen_patients:
            unique_patients.append(appointment)
            seen_patients.add(appointment.patient.id)
    
    # Get all prescriptions for this doctor's patients with their medicines
    prescriptions = Prescription.objects.filter(doctor=doctor).select_related('patient', 'appointment').prefetch_related('medicines')
    
    context = {
        'user': doctor,
        'completed_appointments': unique_patients,  # Now contains unique patients with their latest completed appointments
        'prescriptions': prescriptions,
        'search_query': search_query,
    }
    return render(request, 'doctor/patients.html', context)



def get_patient_appointments_api(request, patient_id):
    """API endpoint to get patient appointment history"""
    user_id = request.session.get('doctor_id')
    if not user_id:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        patient = Patient.objects.get(id=patient_id)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return JsonResponse({'error': 'Patient or doctor not found'}, status=404)
    
    # Get all appointments for this patient with this doctor
    appointments = Appointment.objects.filter(
        patient=patient,
        doctor=doctor
    ).order_by('-appointment_date')
    
    appointment_data = []
    for appointment in appointments:
        appointment_data.append({
            'id': appointment.id,
            'date': appointment.appointment_date.strftime('%B %d, %Y'),
            'time': appointment.appointment_time.strftime('%I:%M %p'),
            'reason': appointment.reason_for_visit,
            'status': appointment.get_status_display(),
            'status_key': appointment.status
        })
    
    return JsonResponse({
        'appointments': appointment_data,
        'count': len(appointment_data)
    })


def get_patient_prescriptions_api(request, patient_id):
    """API endpoint to get patient prescription history"""
    user_id = request.session.get('doctor_id')
    if not user_id:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        patient = Patient.objects.get(id=patient_id)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return JsonResponse({'error': 'Patient or doctor not found'}, status=404)
    
    # Get all prescriptions for this patient from this doctor
    prescriptions = Prescription.objects.filter(
        patient=patient,
        doctor=doctor
    ).prefetch_related('medicines').order_by('-created_at')
    
    prescription_data = []
    for prescription in prescriptions:
        medicines = []
        for medicine in prescription.medicines.all():
            medicines.append({
                'name': medicine.drug_name_generic,
                'strength': medicine.strength,
                'dosage': medicine.dosage_frequency
            })
        
        prescription_data.append({
            'id': prescription.id,
            'date': prescription.created_at.strftime('%B %d, %Y'),
            'medicines': medicines,
            'next_appointment': prescription.next_appointment_date.strftime('%B %d, %Y') if prescription.next_appointment_date else None
        })
    
    return JsonResponse({
        'prescriptions': prescription_data,
        'count': len(prescription_data)
    })


def get_patient_lab_tests_api(request, patient_id):
    """API endpoint to get patient lab test history"""
    user_id = request.session.get('doctor_id')
    if not user_id:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        patient = Patient.objects.get(id=patient_id)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return JsonResponse({'error': 'Patient or doctor not found'}, status=404)
    
    # Get all prescriptions with lab tests for this patient from this doctor
    prescriptions_with_tests = Prescription.objects.filter(
        patient=patient,
        doctor=doctor,
        lab_tests__isnull=False
    ).prefetch_related('lab_tests').order_by('-created_at')
    
    lab_test_data = []
    for prescription in prescriptions_with_tests:
        for lab_test in prescription.lab_tests.all():
            lab_test_data.append({
                'id': lab_test.id,
                'name': lab_test.test_name,
                'category': lab_test.get_test_category_display(),
                'priority': lab_test.get_priority_display(),
                'instructions': lab_test.instructions,
                'date': prescription.created_at.strftime('%B %d, %Y')
            })
    
    return JsonResponse({
        'lab_tests': lab_test_data,
        'count': len(lab_test_data)
    })



def doctor_view_patient_records(request, patient_id):
    """View for doctors to access their patients' medical records"""
    doctor_id = request.session.get('doctor_id')
    if not doctor_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
    except Doctor.DoesNotExist:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect('doctor_patients')
    
    # Verify that this patient has had appointments with this doctor
    has_appointment = Appointment.objects.filter(
        patient=patient, 
        doctor=doctor
    ).exists()
    
    if not has_appointment:
        messages.error(request, "Access denied. You can only view records of your patients.")
        return redirect('doctor_patients')
    
    # Get lab report images for this patient
    lab_reports = LabReportImage.objects.filter(patient=patient).order_by('-uploaded_at')
    
    # Get appointment history for this patient with this doctor
    appointments = Appointment.objects.filter(
        patient=patient,
        doctor=doctor
    ).order_by('-appointment_date', '-appointment_time')
    
    # Get medical conditions for this patient
    medical_conditions = MedicalCondition.objects.filter(patient=patient).order_by('-created_at')
    
    # Get past operations for this patient
    past_operations = PastOperation.objects.filter(patient=patient).order_by('-created_at')
    
    return render(request, 'doctor/records.html', {
        'user': doctor,  # Pass the doctor object as the user context
        'doctor_viewing': True,  # Flag to indicate this is being viewed by a doctor
        'doctor': doctor,
        'lab_reports': lab_reports,
        'patient_details': patient,  # Include patient details
        'appointments': appointments,  # Include appointment history
        'medical_conditions': medical_conditions,  # Include medical conditions
        'past_operations': past_operations  # Include past operations
    })


def doctor_patient_records_api(request, patient_id):
    """API endpoint to get patient records for the modal"""
    doctor_id = request.session.get('doctor_id')
    if not doctor_id:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        patient = Patient.objects.get(id=patient_id)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return JsonResponse({'error': 'Patient or doctor not found'}, status=404)
    
    # Verify that this patient has had appointments with this doctor
    has_appointment = Appointment.objects.filter(
        patient=patient, 
        doctor=doctor
    ).exists()
    
    if not has_appointment:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get appointment history
    appointments = Appointment.objects.filter(
        patient=patient,
        doctor=doctor
    ).order_by('-appointment_date', '-appointment_time').values(
        'id', 'appointment_date', 'appointment_time', 'reason_for_visit', 'status'
    )
    
    # Get medical conditions
    medical_conditions = MedicalCondition.objects.filter(
        patient=patient
    ).order_by('-created_at').values(
        'id', 'condition_name', 'diagnosis_date', 'description', 'status'
    )
    
    # Get past operations
    past_operations = PastOperation.objects.filter(
        patient=patient
    ).order_by('-created_at').values(
        'id', 'operation_name', 'operation_date', 'surgeon', 'hospital_clinic', 'description'
    )
    
    # Get lab reports
    lab_reports = LabReportImage.objects.filter(
        patient=patient
    ).order_by('-uploaded_at').values(
        'id', 'report_name', 'uploaded_at', 'image', 'notes'
    )
    
    # Get prescriptions for this patient from this doctor
    prescriptions = Prescription.objects.filter(
        patient=patient,
        doctor=doctor
    ).prefetch_related('medicines').order_by('-created_at')
    
    # Convert QuerySets to lists and add file_extension for lab reports
    lab_reports_list = []
    for report in lab_reports:
        import os
        _, ext = os.path.splitext(report['image'])
        lab_reports_list.append({
            'id': report['id'],
            'report_name': report['report_name'],
            'uploaded_at': report['uploaded_at'].isoformat() if report['uploaded_at'] else None,
            'image': report['image'],
            'notes': report['notes'],
            'file_extension': ext.lower() if ext else ''
        })
    
    # Convert prescriptions to list
    prescriptions_list = []
    for prescription in prescriptions:
        medicines_list = []
        for medicine in prescription.medicines.all():
            medicines_list.append({
                'id': medicine.id,
                'drug_name_generic': medicine.drug_name_generic,
                'drug_name_brand': medicine.drug_name_brand or '',
                'strength': medicine.strength,
                'dosage_frequency': medicine.dosage_frequency,
                'instructions': medicine.instructions,
                'duration_days': medicine.duration_days
            })
        
        prescriptions_list.append({
            'id': prescription.id,
            'date': prescription.created_at.isoformat() if prescription.created_at else None,
            'created_at_formatted': prescription.created_at.strftime('%B %d, %Y') if prescription.created_at else None,
            'medicines': medicines_list,
            'next_appointment_date': prescription.next_appointment_date.isoformat() if prescription.next_appointment_date else None
        })
    
    # Get prescribed lab tests
    prescribed_lab_tests = []
    prescriptions_with_tests = Prescription.objects.filter(
        patient=patient,
        doctor=doctor
    ).prefetch_related('lab_tests').order_by('-created_at')
    
    for prescription in prescriptions_with_tests:
        for lab_test in prescription.lab_tests.all():
            prescribed_lab_tests.append({
                'id': lab_test.id,
                'name': lab_test.test_name,
                'category': lab_test.get_test_category_display(),
                'priority': lab_test.get_priority_display(),
                'instructions': lab_test.instructions,
                'date': prescription.created_at.strftime('%B %d, %Y')
            })

    return JsonResponse({
        'patient': {
            'first_name': patient.first_name,
            'last_name': patient.last_name,
            'email': patient.email,
            'blood_group': patient.blood_group,
            'gender': patient.gender,
            'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            'phone_number': patient.phone_number
        },
        'appointments': list(appointments),
        'medical_conditions': list(medical_conditions),
        'prescribed_lab_tests': prescribed_lab_tests,
        'lab_reports': lab_reports_list,
        'prescriptions': prescriptions_list,
        'prescriptions_count': len(prescriptions_list)
    })


def add_prescription(request):
    """API endpoint to add a prescription for a patient"""
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            
            # PrescriptionMedicine model fields
            drug_name_generic = data.get('drug_name_generic', '').strip()
            drug_name_brand = data.get('drug_name_brand', '').strip()
            strength = data.get('strength', '').strip()
            dosage_frequency = data.get('dosage_frequency', '').strip()
            instructions = data.get('instructions', '').strip()
            duration_days = data.get('duration_days')
            if duration_days:
                try:
                    duration_days = int(duration_days)
                except (ValueError, TypeError):
                    duration_days = None
            
            # Validate required fields
            if not patient_id or not drug_name_generic or not dosage_frequency or not instructions or not duration_days:
                return JsonResponse({
                    'error': 'All required fields must be filled: Medicine name, dosage, instructions, and duration'
                }, status=400)
            
            # Get doctor from session
            doctor_id = request.session.get('doctor_id')
            if not doctor_id:
                return JsonResponse({'error': 'Unauthorized'}, status=401)
            
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                patient = Patient.objects.get(id=patient_id)
            except (Doctor.DoesNotExist, Patient.DoesNotExist):
                return JsonResponse({'error': 'Doctor or patient not found'}, status=404)
            
            # Verify that this patient has had appointments with this doctor
            has_appointment = Appointment.objects.filter(
                patient=patient, 
                doctor=doctor
            ).exists()
            
            if not has_appointment:
                return JsonResponse({'error': 'Access denied. You can only prescribe to your patients.'}, status=403)
            
            # Create prescription
            prescription = Prescription.objects.create(
                doctor=doctor,
                patient=patient
            )
            
            # Create prescription medicine 
            PrescriptionMedicine.objects.create(
                prescription=prescription,
                drug_name_generic=drug_name_generic,
                drug_name_brand=drug_name_brand if drug_name_brand else None,
                strength=strength if strength else None,
                dosage_frequency=dosage_frequency,
                instructions=instructions,
                duration_days=duration_days
            )
            
            # Log the action
            AuditLog.objects.create(
                user=doctor.user,
                action='prescription_created',
                details=f'Prescription created for {patient.first_name} {patient.last_name}: {drug_name_generic}',
                related_object_id=prescription.id,
                related_object_type='Prescription'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Prescription added successfully',
                'prescription_id': prescription.id
            })
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def add_lab_test(request, patient_id):
    """View to add lab tests for a patient (Handles both AJAX and regular requests)"""
    doctor_id = request.session.get('doctor_id')
    if not doctor_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        patient = Patient.objects.get(id=patient_id)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Doctor or patient not found'}, status=404)
        messages.error(request, "Doctor or patient not found.")
        return redirect('doctor_patients')

    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            import json
            try:
                data = json.loads(request.body)
                tests = data.get('tests', [])
                
                if not tests:
                    return JsonResponse({'error': 'Please add at least one lab test.'}, status=400)
                
                # Create a prescription to link the lab tests to
                prescription = Prescription.objects.create(
                    doctor=doctor,
                    patient=patient
                )
                
                for test_data in tests:
                    test_name = test_data.get('name')
                    category = test_data.get('category')
                    priority = test_data.get('priority')
                    instructions = test_data.get('instructions')
                    
                    if test_name:
                        LabTest.objects.create(
                            prescription=prescription,
                            test_name=test_name,
                            test_category=category,
                            priority=priority,
                            instructions=instructions
                        )
                
                # Log the action
                AuditLog.objects.create(
                    user=doctor.user,
                    action='prescription_created',
                    details=f'Lab test prescription created for {patient.first_name} {patient.last_name}',
                    related_object_id=prescription.id,
                    related_object_type='Prescription'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Lab tests successfully prescribed for {patient.first_name}.'
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON data'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        
        # Legacy regular form submission (keep for compatibility if needed, though we'll use AJAX)
        lab_test_count = int(request.POST.get('lab_test_count', 0))
        if lab_test_count > 0:
            prescription = Prescription.objects.create(doctor=doctor, patient=patient)
            for i in range(lab_test_count):
                test_name = request.POST.get(f'lab_test_{i}_name')
                if test_name:
                    LabTest.objects.create(
                        prescription=prescription,
                        test_name=test_name,
                        test_category=request.POST.get(f'lab_test_{i}_category'),
                        priority=request.POST.get(f'lab_test_{i}_priority'),
                        instructions=request.POST.get(f'lab_test_{i}_instructions')
                    )
            messages.success(request, f"Lab tests successfully prescribed for {patient.first_name}.")
            return redirect('doctor_patients')
    
    return render(request, 'doctor/add_lab_test.html', {'doctor': doctor, 'patient': patient})


def add_medical_condition(request):
    """API endpoint to add a medical condition for a patient"""
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            condition_name = data.get('condition_name', '').strip()
            diagnosis_date = data.get('diagnosis_date')
            description = data.get('description', '').strip()
            status = data.get('status', 'active')
            notes = data.get('notes', '').strip()
            
            if not patient_id or not condition_name or not diagnosis_date:
                return JsonResponse({'error': 'Patient ID, condition name, and diagnosis date are required'}, status=400)
            
            try:
                patient = Patient.objects.get(id=patient_id)
            except Patient.DoesNotExist:
                return JsonResponse({'error': 'Patient not found'}, status=404)
            
            medical_condition = MedicalCondition.objects.create(
                patient=patient,
                condition_name=condition_name,
                diagnosis_date=diagnosis_date,
                description=description if description else None,
                status=status,
                notes=notes if notes else None
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Medical condition added successfully',
                'condition_id': medical_condition.id
            })
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def add_past_operation(request):
    """API endpoint to add a past operation for a patient"""
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            operation_name = data.get('operation_name', '').strip()
            operation_date = data.get('operation_date')
            surgeon = data.get('surgeon', '').strip()
            hospital_clinic = data.get('hospital_clinic', '').strip()
            description = data.get('description', '').strip()
            notes = data.get('notes', '').strip()
            
            if not patient_id or not operation_name or not operation_date:
                return JsonResponse({'error': 'Patient ID, operation name, and operation date are required'}, status=400)
            
            try:
                patient = Patient.objects.get(id=patient_id)
            except Patient.DoesNotExist:
                return JsonResponse({'error': 'Patient not found'}, status=404)
            
            past_operation = PastOperation.objects.create(
                patient=patient,
                operation_name=operation_name,
                operation_date=operation_date,
                surgeon=surgeon if surgeon else None,
                hospital_clinic=hospital_clinic if hospital_clinic else None,
                description=description if description else None,
                notes=notes if notes else None
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Past operation added successfully',
                'operation_id': past_operation.id
            })
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def check_medicine_stock(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            medicine_name = data.get('medicine_name', '').lower().strip()
            
            if not medicine_name:
                return JsonResponse({'error': 'Medicine name is required'}, status=400)
            
            # Check if any medicine with this generic name exists in the database
            # and has quantity greater than 0 and is not expired
            from django.utils import timezone
            
            # Check if any medicine matches the generic name, is in stock, and not expired
            medicine_exists = Medicine.objects.filter(
                generic_name__icontains=medicine_name,
                quantity__gt=0,  # quantity greater than 0 means in stock
                expiry_date__gt=timezone.now().date()  # not expired
            ).exists()
            
            # Also check for medicines with matching brand name, in stock, and not expired
            brand_exists = Medicine.objects.filter(
                brand_name__icontains=medicine_name,
                quantity__gt=0,
                expiry_date__gt=timezone.now().date()  # not expired
            ).exists()
            
            # If neither exists or both have zero quantity or are expired, consider it out of stock
            out_of_stock = not (medicine_exists or brand_exists)
            
            return JsonResponse({
                'medicine_name': medicine_name,
                'out_of_stock': out_of_stock,
                'in_stock': not out_of_stock
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def update_doctor_status(request):
    if request.method == 'POST':
        import json
        try:
            # Get doctor from session
            user_id = request.session.get('doctor_id')
            if not user_id:
                return JsonResponse({'error': 'Not authenticated'}, status=401)
            
            try:
                doctor = Doctor.objects.get(id=user_id)
            except Doctor.DoesNotExist:
                return JsonResponse({'error': 'Doctor not found'}, status=404)
            
            # Parse JSON data
            data = json.loads(request.body)
            new_status = data.get('status', '').lower()
            
            # Validate status
            valid_statuses = ['active', 'inactive', 'leave']
            if new_status not in valid_statuses:
                return JsonResponse({'error': 'Invalid status'}, status=400)
            
            # Update doctor status
            doctor.availability_status = new_status
            doctor.save()
            
            return JsonResponse({
                'success': True,
                'status': new_status,
                'message': f'Status updated to {new_status.capitalize()}'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def set_doctor_leave(request):
    if request.method == 'POST':
        user_id = request.session.get('doctor_id')
        if not user_id:
            messages.error(request, 'You must be logged in as a doctor to set leave.')
            return redirect('login')
        
        try:
            doctor = Doctor.objects.get(id=user_id)
        except Doctor.DoesNotExist:
            messages.error(request, 'Doctor not found.')
            return redirect('login')
        
        form = LeaveForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.doctor = doctor
            leave.save()
            
            # Update doctor's availability status to 'leave' for the leave period
            # This will be handled by the automatic status management
            messages.success(request, 'Leave has been set successfully!')
        else:
            messages.error(request, 'Please correct the errors below.')
            
        return redirect('doctor_dashboard')
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def test_doctor_status(request):
    """Test view to verify doctor availability status functionality"""
    doctors = Doctor.objects.all()[:3]  # Get first 3 doctors for testing
    
    test_data = []
    for doctor in doctors:
        test_data.append({
            'id': doctor.id,
            'name': f"Dr. {doctor.first_name} {doctor.last_name}",
            'availability_status': doctor.availability_status,
            'get_availability_status_display': doctor.get_availability_status_display(),
            'consulting_time_from': doctor.consulting_time_from,
            'consulting_time_to': doctor.consulting_time_to,
        })
    
    return JsonResponse({'doctors': test_data})


def admin_audit_logs(request):
    """Admin view to see system audit logs"""
    # Ensure admin authentication
    if not request.session.get('admin_id'):
        return redirect('login')
    
    # Get filter parameters
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Get all audit logs with related user information
    logs = AuditLog.objects.select_related('user').all()
    
    # Apply filters
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if user_filter:
        logs = logs.filter(user__id=user_filter)
    
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    # Get all users for filter dropdown
    all_users = Users.objects.all().order_by('role', 'id')
    
    # Pre-process all users for filter dropdown
    processed_all_users = []
    for user in all_users:
        user_data = {
            'user': user,
            'display_name': user.get_user_display_name()
        }
        processed_all_users.append(user_data)
    
    context = {
        'logs': logs,
        'all_users': processed_all_users,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin/audit_logs.html', context)






def prescription_details(request, prescription_id):
    """View prescription details in a printable format"""
    doctor_id = request.session.get('doctor_id')
    if not doctor_id:
        return redirect('login')
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        prescription = Prescription.objects.select_related('doctor', 'patient', 'appointment').prefetch_related('medicines').get(
            id=prescription_id,
            doctor=doctor
        )
    except (Doctor.DoesNotExist, Prescription.DoesNotExist):
        messages.error(request, "Prescription not found.")
        return redirect('doctor_patients')
    
    return render(request, 'doctor/prescription_details.html', {
        'prescription': prescription,
        'doctor': doctor
    })


def delete_prescription(request, prescription_id):
    user_id = request.session.get('doctor_id')
    if not user_id:
        return redirect('login')
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        doctor = Doctor.objects.get(id=user_id)
        prescription = Prescription.objects.get(id=prescription_id, doctor=doctor)
        
        # Log prescription deletion
        try:
            if doctor.user:
                user_model = Users.objects.get(id=doctor.user.id, role='doctor')
                log_user_action(
                    user_model,
                    'prescription_deleted',
                    f'Deleted prescription for patient {prescription.patient.first_name} {prescription.patient.last_name}',
                    related_object=prescription,
                    request=request
                )
            else:
                # Doctor doesn't have a corresponding Users record, skip logging
                pass
        except Users.DoesNotExist:
            # Doctor doesn't have a corresponding Users record, skip logging
            pass
        except Exception as e:
            print(f"Error logging prescription deletion: {e}")
        
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
    doctor_form = DoctorRegistrationForm()
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

        elif role == 'doctor':
            doctor_form = DoctorRegistrationForm(request.POST)
            if doctor_form.is_valid():
                user_role = Users.objects.create(role='doctor')
                doctor = doctor_form.save(commit=False)
                doctor.user = user_role
                doctor.registration_status = 'pending'
                doctor.save()
                registered = True
                messages.success(request, "Registration successful! Your account is pending admin approval.")

    # This context now contains the forms with their respective errors
    context = {
        'patient_form': patient_form,
        'pharmacist_form': pharmacist_form,
        'doctor_form': doctor_form,
        'registered': registered,
        'role': role if registered else None
    }
    return render(request, 'register.html', context)

import threading
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse

def send_doctor_status_email(email,name,status):
    display_status=status.title()
    subject=f"Mediwise Update: Application Status - {display_status}"
    status_configs = {
        "approved": {
            "title": "Application Approved",
            "color": "#10B981",  # Emerald Green
            "bg_light": "#ECFDF5",
            "icon": "✅",
            "message": f"Welcome to the network, Dr. {name}! Your credentials have been verified. You can now begin accepting digital consultations and accessing patient records.",
            "cta_text": "Launch MediWise Portal"
        },
        "rejected": {
            "title": "Application Declined",
            "color": "#EF4444",  # Professional Red
            "bg_light": "#FEF2F2",
            "icon": "❌",
            "message": f"Dear Dr. {name}, thank you for your interest in MediWise. At this time, we are unable to move forward with your professional application.",
            "cta_text": "Review Guidelines"
        },
        "pending": {
            "title": "Review in Progress",
            "color": "#F59E0B",  # Amber
            "bg_light": "#FFFBEB",
            "icon": "⏳",
            "message": f"Dear Dr. {name}, your application is currently in the 'Pending' queue. Our compliance team is verifying your medical license and board certifications.",
            "cta_text": "View Application Status"
        }
    }

    # Fetch config based on status; default to 'pending' if status is unknown
    config = status_configs.get(status.lower(), status_configs["pending"])

    # 3. High-End MediWise UI Design (Clean Version)
    html_content = f"""
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 20px auto; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);">
        
        <div style="background: linear-gradient(135deg, #1E40AF 0%, #1e3a8a 100%); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">MediWise</h1>
            <p style="color: #93c5fd; margin: 5px 0 0 0; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Professional Healthcare Network</p>
        </div>

        <div style="padding: 40px 35px; background-color: #ffffff;">
            <h2 style="color: #111827; margin-top: 0; font-size: 22px;">Application Status Update</h2>
            
            <div style="background-color: {config['bg_light']}; border: 1px solid {config['color']}; padding: 20px; border-radius: 8px; text-align: center; margin: 25px 0;">
                <div style="font-size: 32px; margin-bottom: 10px;">{config['icon']}</div>
                <h3 style="color: {config['color']}; margin: 0; text-transform: uppercase; font-size: 16px; font-weight: 700;">{config['title']}</h3>
            </div>

            <p style="font-size: 16px; line-height: 1.6; color: #4b5563;">
                {config['message']}
            </p>
            
            <div style="text-align: center; margin: 40px 0;">
                <a href="http://127.0.0.1:8000/" style="background-color: #1e3a8a; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; display: inline-block;">
                    {config['cta_text']}
                </a>
            </div>

            <p style="font-size: 13px; color: #6b7280; text-align: center;">
                Need help? Contact the MediWise Support Team at support@mediwise.com
            </p>
        </div>

        <div style="background-color: #f9fafb; padding: 20px; text-align: center; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
            <p style="margin: 0;">This email was sent to confirm your status on the MediWise platform.</p>
            <p style="margin: 5px 0 0 0;">&copy; 2026 MediWise Inc. All Rights Reserved.</p>
        </div>
    </div>
    """

    def send_email_thread():
        try:
            send_mail(
                subject=subject,
                message=config['message'],
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_content,
                fail_silently=False,

            )
        except Exception as e:
            print(f"Failed to send email to {email}: {e}")
    threading.Thread(target=send_email_thread, daemon=True).start()

    return JsonResponse({'status':'success','message':f'Status Update send to Dr.{name}.'})
def manage_doctors(request):
    # Ensure admin authentication
    if not request.session.get('admin_id'):
        return redirect('login')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            doctor_id = request.POST.get('doctor_id')
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                doctor.registration_status = 'approved'
                doctor.save()
                
                
                try:
                    send_doctor_status_email(doctor.email,doctor.first_name,doctor.registration_status)
                except Exception as e:
                    # Log the error but don't prevent approval
                    print(f"Failed to send approval email: {e}")
                
                messages.success(request, f"Doctor {doctor.first_name} {doctor.last_name} approved successfully and notification sent!")
            except Doctor.DoesNotExist:
                messages.error(request, "Doctor not found.")
                
        elif action == 'reject':
            doctor_id = request.POST.get('doctor_id')
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                doctor.registration_status = 'rejected'
                doctor.save()
                try:
                    send_doctor_status_email(doctor.email,doctor.first_name,doctor.registration_status)
                except Exception as e:
                    # Log the error but don't prevent approval
                    print(f"Failed to send approval email: {e}")
                
                messages.warning(request, f"Doctor {doctor.first_name} {doctor.last_name} registration rejected.")
            except Doctor.DoesNotExist:
                messages.error(request, "Doctor not found.")
                
        elif action == 'edit':
            doctor_id = request.POST.get('doctor_id')
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                old_status = doctor.registration_status
                form = DoctorRegistrationForm(request.POST, instance=doctor)
                
                if form.is_valid():
                    updated_doctor = form.save()
                    if doctor.registration_status in ['approved','rejected','pending']:
                        send_doctor_status_email(doctor.email,doctor.first_name,doctor.registration_status)
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

def manage_pharmacies(request):
    # Ensure admin authentication
    if not request.session.get('admin_id'):
        return redirect('login')
    
    # Get all pharmacists with their pharmacy information
    pharmacists = Pharmacist.objects.all().order_by('-registration_date')
    
    return render(request, 'admin/pharmacies.html', {
        'pharmacists': pharmacists
    })

def pharmacy_details(request, pharmacist_id):
    # Ensure admin authentication
    if not request.session.get('admin_id'):
        return redirect('login')
    
    try:
        pharmacist = Pharmacist.objects.get(id=pharmacist_id)
    except Pharmacist.DoesNotExist:
        messages.error(request, "Pharmacy not found.")
        return redirect('manage_pharmacies')
    
    from django.db.models import Sum, F, Count
    
    # Get total medicines count
    total_medicines = Medicine.objects.filter(pharmacist=pharmacist).count()
    active_medicines = Medicine.objects.filter(pharmacist=pharmacist, quantity__gt=0).count()
    low_stock_medicines = Medicine.objects.filter(pharmacist=pharmacist, quantity__lte=10).count()
    
    # Get total orders and revenue for this pharmacist's medicines
    order_items = OrderItem.objects.filter(medicine__pharmacist=pharmacist)
    total_orders = order_items.count()
    total_revenue = order_items.aggregate(total=Sum(F('quantity') * F('price_at_order')))['total'] or 0
    
    # Get recent orders (last 10)
    recent_orders = order_items.select_related('order__patient', 'medicine').order_by('-order__created_at')[:10]
    
    context = {
        'pharmacist': pharmacist,
        'total_medicines': total_medicines,
        'active_medicines': active_medicines,
        'low_stock_medicines': low_stock_medicines,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'recent_orders': recent_orders,
    }
    
    return render(request, 'admin/pharmacy_details.html', context)

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
    writer.writerow(['Brand Name', 'Generic Name', 'Pharmacy', 'Stock', 'Price'])
    
    medicines = Medicine.objects.all()
    for med in medicines:
        writer.writerow([med.brand_name, med.generic_name, med.pharmacist.pharmacy_name, med.quantity, med.price])
        
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
        # Table headers (removed Patient ID)
        data = [['Name', 'Phone', 'Email', 'Gender', 'Date of Birth', 'Blood Group', 'Address']]
        
        # Add patient data
        for patient in patients:
            dob = patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else 'N/A'
            email = patient.email if patient.email else 'N/A'
            phone = patient.phone_number if patient.phone_number else 'N/A'
            gender = patient.gender if patient.gender else 'N/A'
            blood_group = patient.blood_group if patient.blood_group else 'N/A'
            address = patient.address if patient.address else 'N/A'
            
            data.append([
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


def export_orders_pdf(request):
    """Generate and download a PDF report of all orders with pharmacy and customer information"""
    if not request.session.get('admin_id'):
        return redirect('login')
    
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from io import BytesIO
    from datetime import datetime
    
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
    title = Paragraph("Orders Report", title_style)
    elements.append(title)
    
    # Date
    date_para = Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", header_style)
    elements.append(date_para)
    elements.append(Spacer(1, 20))
    
    # Get all orders with related information - ordered by date (oldest first)
    from .models import Order, OrderItem
    orders = Order.objects.select_related('patient').prefetch_related(
        'items__medicine__pharmacist'
    ).order_by('created_at')  # Changed to ascending order (first to last)
    
    if orders.exists():
        # Table headers - changed "Order ID" to "Sl.No."
        data = [['Sl.No.', 'Customer Name', 'Pharmacy Name', 'Total Price', 'Order Date', 'Status']]
        
        # Add order data with serial numbers
        for index, order in enumerate(orders, start=1):
            # Get pharmacy name from order items
            pharmacy_name = 'N/A'
            if order.items.exists():
                first_item = order.items.first()
                if first_item.medicine and first_item.medicine.pharmacist:
                    pharmacy_name = first_item.medicine.pharmacist.pharmacy_name or 'N/A'
            
            customer_name = f"{order.patient.first_name} {order.patient.last_name}" if order.patient else 'N/A'
            order_date = order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else 'N/A'
            status_display = order.get_status_display() if hasattr(order, 'get_status_display') else order.status
            
            data.append([
                str(index),  # Serial number instead of order ID
                customer_name,
                pharmacy_name,
                f"{order.total_amount:.2f}",
                order_date,
                status_display
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
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef2f2')]),  # Alternating row colors
        ]))
        
        elements.append(table)
        
        # Add order count summary
        elements.append(Spacer(1, 20))
        summary_text = f"Total Orders: {orders.count()}"
        summary_para = Paragraph(summary_text, header_style)
        elements.append(summary_para)
        
        # Add total revenue
        total_revenue = sum(order.total_amount for order in orders)
        revenue_text = f"Total Revenue: {total_revenue:.2f}"
        revenue_para = Paragraph(revenue_text, header_style)
        elements.append(revenue_para)
    else:
        # No orders message
        no_orders = Paragraph("No orders found.", header_style)
        elements.append(no_orders)
    
    # Build the PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="orders_report.pdf"'
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


def payment_portal(request):
    """Display payment portal for pending orders"""
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Check if there's a pending order in session
    pending_order = request.session.get('pending_order')
    if not pending_order:
        messages.error(request, "No pending order found.")
        return redirect('view_cart')
    
    # Get pharmacist information from cart items for in-store pickup
    shop_location = None
    cart_items_ids = [item['id'] for item in pending_order['cart_items']]
    
    # Fetch actual cart items from database
    cart_items = Cart.objects.filter(id__in=cart_items_ids, patient=patient)
    
    if cart_items.exists():
        # Get the first medicine's pharmacist (assuming all medicines are from same pharmacist)
        first_item = cart_items.first()
        if first_item and hasattr(first_item, 'medicine'):
            pharmacist = first_item.medicine.pharmacist
            if pharmacist:
                shop_location = {
                    'pharmacy_name': pharmacist.pharmacy_name,
                    'address': pharmacist.address,
                    'phone_number': pharmacist.phone_number
                }
    
    context = {
        'user': patient,
        'cart_items': cart_items,
        'subtotal': pending_order['subtotal'],
        'gst_amount': pending_order['gst_amount'],
        'total_amount': pending_order['total_amount'],
        'shop_location': shop_location
    }
    
    return render(request, 'patient/payment_portal.html', context)


def process_payment(request):
    """Process the payment and create order"""
    import uuid
    from decimal import Decimal
    
    if request.method != 'POST':
        return redirect('payment_portal')
    
    patient_id = request.session.get('patient_id')
    if not patient_id:
        return redirect('login')
    
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return redirect('login')
    
    # Get pending order from session
    pending_order = request.session.get('pending_order')
    if not pending_order:
        messages.error(request, "No pending order found.")
        return redirect('view_cart')
    
    # Get payment details
    card_name = request.POST.get('card_name', '').strip()
    card_number = request.POST.get('card_number', '').replace(' ', '')
    card_cvv = request.POST.get('card_cvv', '').strip()
    
    # Validate payment details (basic validation)
    if not card_name or not card_number or not card_cvv:
        messages.error(request, "Please fill in all payment details.")
        return redirect('payment_portal')
    
    if len(card_number) < 16:
        messages.error(request, "Invalid card number.")
        return redirect('payment_portal')
    
    if len(card_cvv) < 3:
        messages.error(request, "Invalid CVV.")
        return redirect('payment_portal')
    
    # Create Order
    order = Order.objects.create(
        patient=patient,
        total_amount=Decimal(str(pending_order['total_amount'])),
        gst_amount=Decimal(str(pending_order['gst_amount'])),
        status='pending',  # Set status to successful upon successful payment
    )
    
    # Log the successful order for earnings tracking
    log_user_action(
        patient.user if hasattr(patient, 'user') else None,
        'order_completed',
        f'Order #{order.id} created and marked as successful. Earnings: ₹{order.total_amount}',
        related_object=order,
        request=request
    )
    
    # Create Order Items and Update Stock
    for item_data in pending_order['cart_items']:
        try:
            medicine = Medicine.objects.get(id=item_data['medicine_id'])
            if medicine.quantity < item_data['quantity']:
                messages.error(request, f"Not enough stock for {medicine.brand_name}.")
                order.delete()  # Clean up the order
                return redirect('view_cart')
            
            OrderItem.objects.create(
                order=order,
                medicine=medicine,
                quantity=item_data['quantity'],
                price_at_order=Decimal(str(item_data['price']))
            )
            medicine.quantity -= item_data['quantity']
            medicine.save()
        except Medicine.DoesNotExist:
            messages.error(request, "One or more medicines are no longer available.")
            order.delete()  # Clean up the order
            return redirect('view_cart')
    
    # Create Transaction with card details
    transaction = Transaction.objects.create(
        order=order,
        transaction_id=f"MW-{uuid.uuid4().hex[:8].upper()}",
        amount=Decimal(str(pending_order['total_amount'])),
        card_name=card_name,
        card_number=card_number[-4:].rjust(len(card_number), '*'),  # Store only last 4 digits
        card_cvv='***'  # Don't store actual CVV
    )
    
    # Clear cart items
    cart_item_ids = [item['id'] for item in pending_order['cart_items']]
    Cart.objects.filter(id__in=cart_item_ids).delete()
    
    # Create notifications for pharmacists whose medicines were ordered
    from .models import Notification
    pharmacists_notified = set()
    for item_data in pending_order['cart_items']:
        try:
            medicine = Medicine.objects.get(id=item_data['medicine_id'])
            pharmacist = medicine.pharmacist
            if pharmacist and pharmacist.id not in pharmacists_notified:
                Notification.objects.create(
                    pharmacist=pharmacist,
                    notification_type='order_status',
                    title='New Order Received',
                    message=f'A new order #{order.id} has been placed for medicines from your pharmacy.',
                    related_id=order.id
                )
                pharmacists_notified.add(pharmacist.id)
        except Medicine.DoesNotExist:
            pass
    
    # Clear session data
    if 'pending_order' in request.session:
        del request.session['pending_order']
    
    messages.success(request, "Payment successful! Your order has been placed.")
    return redirect('view_order_receipt', order_id=order.id)

def generate_receipt_pdf(request, order_id):
    """Generate and return a PDF receipt for an order"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from io import BytesIO
    import os
    
    try:
        order = Order.objects.get(id=order_id)
        patient = order.patient
        
        # Create a BytesIO buffer to receive PDF data
        buffer = BytesIO()
        
        # Create the PDF object, using the buffer as its "file."
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom header style
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.Color(0.73, 0.07, 0.24),  # Rose color
        )
        
        # Title
        title = Paragraph("PAYMENT RECEIPT", header_style)
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Company Info
        company_info = [
            ['Mediwise Healthcare', 'Transaction ID:', order.transaction.transaction_id],
            ['', 'Date:', order.created_at.strftime('%B %d, %Y')],
            ['', 'Time:', order.created_at.strftime('%I:%M %p')],
        ]
        
        t = Table(company_info, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Customer Info
        customer_info = [
            ['Customer Information', 'Payment Details'],
            [f'{patient.first_name} {patient.last_name}', f'Payment Method: Credit Card'],
            [f'{patient.email or "N/A"}', f'Last 4 Digits: ****{order.transaction.card_number[-4:]}'],
            [f'{patient.phone_number or "N/A"}', f'Card Holder: {order.transaction.card_name}'],
        ]
        
        t = Table(customer_info, colWidths=[3*inch, 2.5*inch])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('BACKGROUND', (0, 0), (0, 0), colors.Color(0.95, 0.95, 0.98)),
            ('BACKGROUND', (1, 0), (1, 0), colors.Color(0.95, 0.95, 0.98)),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('SPAN', (0, 0), (0, 0)),
            ('SPAN', (1, 0), (1, 0)),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Order Items Header
        items_header = [['Item', 'Quantity', 'Price', 'Total']]
        items_header_table = Table(items_header, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
        items_header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.73, 0.07, 0.24)),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(items_header_table)
        
        # Order Items
        order_items = []
        for item in order.items.all():
            order_items.append([
                f"{item.medicine.brand_name}<br/>{item.medicine.generic_name}",
                str(item.quantity),
                f"${item.price_at_order}",
                f"${item.get_subtotal()}"
            ])
        
        items_table = Table(order_items, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ]))
        elements.append(items_table)
        
        # Totals
        totals_data = [
            ['', '', 'Subtotal:', f'${order.total_amount - order.gst_amount:.2f}'],
            ['', '', 'GST (18%):', f'${order.gst_amount:.2f}'],
            ['', '', 'Total:', f'${order.total_amount:.2f}'],
        ]
        
        totals_table = Table(totals_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (2, 0), (3, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (2, 0), (3, -1), 10),
            ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(totals_table)
        
        # Thank you message
        elements.append(Spacer(1, 20))
        thank_you = Paragraph(
            "Thank you for choosing Mediwise! We appreciate your trust in our healthcare services.", 
            ParagraphStyle(
                'ThankYou',
                parent=styles['Normal'],
                alignment=1,  # Center alignment
                fontSize=10,
                spaceBefore=10,
                spaceAfter=10,
                textColor=colors.Color(0.5, 0.5, 0.5)
            )
        )
        elements.append(thank_you)
        
        # Build the PDF
        doc.build(elements)
        
        # Get the value of the BytesIO buffer and write it to the response
        pdf = buffer.getvalue()
        buffer.close()
        
        # Create HTTP response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_order_{order.id}.pdf"'
        
        return response
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('patient_dashboard')
    except Exception as e:
        messages.error(request, f"Error generating receipt: {str(e)}")
        return redirect('patient_dashboard')

def view_order_receipt(request, order_id):
    """Display order receipt page with option to download PDF"""
    try:
        order = Order.objects.select_related('patient', 'transaction').prefetch_related('items__medicine').get(id=order_id)
        
        context = {
            'order': order,
            'transaction': order.transaction,
            'patient': order.patient,
        }
        
        return render(request, 'patient/order_receipt.html', context)
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('patient_dashboard')
