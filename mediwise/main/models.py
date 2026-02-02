from django.db import models

# Create your models here.

class Users(models.Model):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
        ('pharmacist', 'Pharmacist'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    id = models.AutoField(primary_key=True)

    def __str__(self):
        return f"{self.role} {self.id}"

class MediAdmin(models.Model):
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True, max_length=100)
    password = models.CharField(max_length=100)

class Patient(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(Users, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    BLOOD_GROUP_CHOICES = (
        ('o+', 'O+'),
        ('o-', 'O-'),
        ('a+', 'A+'),
        ('a-', 'A-'),
        ('b+', 'B+'),
        ('b-', 'B-'),
        ('ab+', 'AB+'),
        ('ab-', 'AB-'),
    )
    blood_group = models.CharField(max_length=20, choices=BLOOD_GROUP_CHOICES, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    height = models.CharField(max_length=10, null=True, blank=True)
    weight = models.CharField(max_length=10, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Pharmacist(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(Users, on_delete=models.CASCADE, null=True, blank=True)
    pharmacy_name = models.CharField(max_length=200, default="Local Pharmacy")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    address = models.TextField()
    registration_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Medicine(models.Model):
    MEDICINE_TYPE_CHOICES = [
        ('OTC', 'Over-the-Counter'),
        ('Rx', 'Prescription Required'),
    ]
    
    pharmacist = models.ForeignKey(Pharmacist, on_delete=models.CASCADE, related_name='medicines')
    brand_name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200)
    strength = models.CharField(max_length=100)
    formulation = models.CharField(max_length=100)
    indications = models.TextField()
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    manufacture_date = models.DateField()
    quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    medicine_type = models.CharField(max_length=3, choices=MEDICINE_TYPE_CHOICES, default='OTC')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand_name} ({self.generic_name})"

class Cart(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='cart_items')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    course_duration = models.CharField(max_length=50, blank=True, null=True, help_text="Expected duration of medicine course")
    requires_prescription = models.BooleanField(default=False, help_text="Indicates if this medicine requires a prescription")
    added_from_prescription = models.BooleanField(default=False, help_text="Indicates if this medicine was added to cart from a prescription")
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.first_name}'s cart - {self.medicine.brand_name}"

class Order(models.Model):
    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('delayed', 'Delayed'),
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.patient.first_name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, related_name='purchase_items')
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2) # Store price in case it changes later
    course_duration = models.CharField(max_length=50, blank=True, null=True, help_text="Expected duration of medicine course")
    reminder_sent_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when refill reminder was sent")

    def get_subtotal(self):
        return self.quantity * self.price_at_order

    def __str__(self):
        return f"{self.quantity}x {self.medicine.brand_name if self.medicine else 'Unknown Medicine'}"

class Transaction(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='transaction')
    transaction_id = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50, default='Card')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TXN {self.transaction_id} for Order #{self.order.id}"

def doctor_profile_image_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/profile_pictures/user_<id>/<filename>
    import os
    ext = filename.split('.')[-1]
    # Generate unique filename using user ID and timestamp
    import uuid
    from datetime import datetime
    filename = f'doctor_{instance.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:8]}.{ext}'
    return os.path.join('profile_pictures', filename)



class Doctor(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(Users, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    address = models.TextField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to=doctor_profile_image_path, null=True, blank=True, max_length=500)
    speciality = models.CharField(max_length=100)
    qualification = models.CharField(max_length=100)
    cureentHospital = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    registration_date = models.DateField(auto_now_add=True)
    consulting_time_from = models.TimeField(null=True, blank=True, help_text="Consulting hours start time")
    consulting_time_to = models.TimeField(null=True, blank=True, help_text="Consulting hours end time")
    location = models.CharField(max_length=200, null=True, blank=True, help_text="Doctor's clinic location")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('confirmed', 'Confirmed'),
        ('rescheduled', 'Rescheduled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateField(help_text="Date of appointment")
    appointment_time = models.TimeField(help_text="Time of appointment")
    reason_for_visit = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Appointment: {self.patient.first_name} {self.patient.last_name} with Dr. {self.doctor.first_name} {self.doctor.last_name} on {self.appointment_date} at {self.appointment_time}"


class Prescription(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='prescriptions')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Prescription for {self.patient.first_name} {self.patient.last_name} - {self.created_at.strftime('%Y-%m-%d')}"


class PrescriptionMedicine(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='medicines')
    drug_name_generic = models.CharField(max_length=200, help_text="Generic name (mandatory)")
    drug_name_brand = models.CharField(max_length=200, blank=True, null=True, help_text="Brand name (optional)")
    strength = models.CharField(max_length=50, help_text="Strength/Potency (e.g., 500mg, 10ml)")
    dosage_frequency = models.CharField(max_length=100, help_text="Dosage & Frequency (e.g., 1 tablet twice a day)")
    route_administration = models.CharField(max_length=50, help_text="Route of Administration (e.g., Oral, Topical, IV)")
    instructions = models.TextField(help_text="Instructions (The \"Sig\") Relation to food and specific timing")
    total_quantity = models.CharField(max_length=50, help_text="Total number of pills or bottles to be dispensed")
    duration_course = models.CharField(max_length=100, help_text="Duration of Course (e.g., \"Take for 90 days\")")
    
    def __str__(self):
        return f"{self.drug_name_generic} - Prescription #{self.prescription.id}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('appointment', 'Appointment'),
        ('refill_reminder', 'Refill Reminder'),
        ('order_status', 'Order Status'),
        ('general', 'General'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when notification was read")
    related_id = models.IntegerField(null=True, blank=True, help_text="ID of related object (appointment, order, etc.)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.patient.first_name} {self.patient.last_name}"


class PrescriptionUpload(models.Model):
    UPLOAD_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('processed', 'Processed'),
        ('partially_available', 'Partially Available'),
        ('not_available', 'Not Available'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='uploaded_prescriptions')
    pharmacist = models.ForeignKey(Pharmacist, on_delete=models.CASCADE, related_name='received_prescriptions', null=True, blank=True, help_text="Pharmacy where prescription was uploaded. Null for common uploads.")
    prescription_image = models.ImageField(upload_to='prescription_uploads/', help_text="Uploaded prescription image")
    notes = models.TextField(blank=True, null=True, help_text="Patient notes about the prescription")
    status = models.CharField(max_length=20, choices=UPLOAD_STATUS_CHOICES, default='pending')
    
    # Extracted medicine information from prescription
    extracted_medicines = models.JSONField(default=list, blank=True, help_text="List of medicines extracted from prescription")
    
    # Availability information
    available_medicines = models.JSONField(default=list, blank=True, help_text="List of available medicines with pharmacy info")
    unavailable_medicines = models.JSONField(default=list, blank=True, help_text="List of unavailable medicines")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        pharmacy_name = self.pharmacist.pharmacy_name if self.pharmacist else "All Pharmacies"
        return f"Prescription Upload by {self.patient.first_name} {self.patient.last_name} - {pharmacy_name}"
    
    @property
    def medicine_availability(self):
        """Check availability of medicines mentioned in prescription"""
        # This will be implemented in the view logic
        return []

class Review(models.Model):
    REVIEW_TYPE_CHOICES = [
        ('doctor', 'Doctor'),
        ('order', 'Order'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reviews')
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPE_CHOICES, default='doctor')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)], help_text="Rating from 1 to 5 stars")
    review_text = models.TextField(blank=True, null=True, help_text="Additional feedback")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.review_type == 'doctor':
            return f"Review by {self.patient.first_name} for Dr. {self.doctor.first_name} - {self.rating} stars"
        else:
            return f"Review by {self.patient.first_name} for Order #{self.order.id} - {self.rating} stars"
