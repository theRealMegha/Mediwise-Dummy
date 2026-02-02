from django import forms
from . models import Patient, Pharmacist, Doctor, Medicine

class PatientRegistrationForm(forms.ModelForm):
    """
    Form for initial patient registration with essential fields
    """
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your last name'
        })
    )
    
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Create a secure password'
        }),
        min_length=8,
        help_text="Password must be at least 8 characters long."
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your email address'
        })
    )

    class Meta:
        model = Patient
        fields = ['email', 'first_name', 'last_name', 'gender', 'password']

    def clean_email(self):
        """Validate that the email is unique"""
        email = self.cleaned_data.get('email')
        if Patient.objects.filter(email=email).exists():
            raise forms.ValidationError("A patient with this email already exists.")
        return email

    def save(self, commit=True):
        """Save the patient instance with the password properly stored"""
        patient = super().save(commit=False)
        # Store the password directly since the Patient model doesn't use Django's built-in password hashing
        patient.password = self.cleaned_data['password']
        
        if commit:
            patient.save()
        return patient

class PatientProfileUpdateForm(forms.ModelForm):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'})
    )
    height = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'})
    )
    weight = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'})
    )

    class Meta:
        model = Patient
        # Include EVERY field you want the user to be able to edit
        fields = ['first_name', 'last_name', 'email', 'gender', 'phone_number', 'address', 'date_of_birth', 'blood_group', 'height', 'weight', 'password']
        
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'phone_number': forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50', 'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50', 'type': 'date'}),
            'blood_group': forms.Select(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'height': forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'weight': forms.TextInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'}),
            'password': forms.PasswordInput(attrs={'class': 'w-full px-4 py-3 pl-12 rounded-xl border border-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 bg-white/50'})
        }

class PharmacistRegistrationForm(forms.ModelForm):
    """
    Form for initial pharmacist registration with essential fields
    """

    pharmacy_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter pharmacy name'
        })
    )
    
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your last name'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Create a secure password'
        }),
        min_length=8,
        help_text="Password must be at least 8 characters long."
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your email address'
        })
    )
    
    license_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your license number'
        })
    )
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your phone number'
        })
    )
    
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'w-full px-4 py-3 rounded-xl border border-pink-200 focus:outline-none focus:ring-2 focus:ring-pink-300 bg-white/50',
            'placeholder': 'Enter your address'
        })
    )

    class Meta:
        model = Pharmacist
        fields = ['email', 'pharmacy_name', 'first_name', 'last_name',  'password', 'license_number', 'phone_number', 'address']

    def clean_email(self):
        """Validate that the email is unique"""
        email = self.cleaned_data.get('email')
        if Pharmacist.objects.filter(email=email).exists():
            raise forms.ValidationError("A pharmacist with this email already exists.")
        return email

    def clean_license_number(self):
        """Validate that the license number is unique"""
        license_number = self.cleaned_data.get('license_number')
        if Pharmacist.objects.filter(license_number=license_number).exists():
            raise forms.ValidationError("A pharmacist with this license number already exists.")
        return license_number

    def save(self, commit=True):
        """Save the pharmacist instance with the password properly stored"""
        pharmacist = super().save(commit=False)
        # Store the password directly since the Pharmacist model doesn't use Django's built-in password hashing
        pharmacist.password = self.cleaned_data['password']
        
        if commit:
            pharmacist.save()
        return pharmacist

class DoctorRegistrationForm(forms.ModelForm):
    # Overriding password to use a PasswordInput widget for security
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter secure password',
            'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'
        }),
        required=False, # Handled in __init__
        help_text="Password must be at least 8 characters."
    )

    class Meta:
        model = Doctor
        # Removed 'password' from fields to prevent auto-overwriting with empty string
        fields = [
            'first_name', 
            'last_name', 
            'email', 
            'phone_number', 
            'speciality', 
            'qualification'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'e.g. John', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'e.g. Smith', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'}),
            'email': forms.EmailInput(attrs={'placeholder': 'doctor@hospital.com', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+1234567890', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'}),
            'speciality': forms.TextInput(attrs={'placeholder': 'e.g. Cardiology', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'}),
            'qualification': forms.TextInput(attrs={'placeholder': 'e.g. MBBS, MD', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-rose-500/20 outline-none transition-all'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If adding a new doctor (no PK), password is required
        if not self.instance.pk:
            self.fields['password'].required = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email exists, EXCLUDING the current instance if editing
        qs = Doctor.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
            
        if qs.exists():
            raise forms.ValidationError("A doctor with this email already exists.")
        return email

    def save(self, commit=True):
        doctor = super().save(commit=False)
        password = self.cleaned_data.get('password')
        
        # If new doctor or password provided, update it
        if password:
            doctor.password = password
        # If editing and no password provided, it keeps the old one automatically 
        # (because we removed it from Meta.fields, super().save() won't touch it)
        
        if commit:
            doctor.save()
        return doctor

class PharmacistProfileUpdateForm(forms.ModelForm):
    password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter new password (optional)',
            'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'
        }),
        help_text="Leave blank to keep current password."
    )

    class Meta:
        model = Pharmacist
        # Removed 'password' from fields
        fields = [
            'pharmacy_name', 'first_name', 'last_name', 'email', 'phone_number', 
            'license_number', 'address'
        ]
        
        widgets = {
            'pharmacy_name': forms.TextInput(attrs={'placeholder': 'Pharmacy Name', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last Name', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email Address', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Phone Number', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'license_number': forms.TextInput(attrs={'placeholder': 'License Number', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Pharmacy Address', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
        }

    def save(self, commit=True):
        pharmacist = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            pharmacist.password = password
        if commit:
            pharmacist.save()
        return pharmacist


class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = [
            'brand_name', 'generic_name', 'strength', 'formulation', 
            'indications', 'batch_number', 'expiry_date', 'manufacture_date', 'quantity', 'price', 'medicine_type'
        ]
        widgets = {
            'brand_name': forms.TextInput(attrs={'placeholder': 'e.g. Panadol', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'generic_name': forms.TextInput(attrs={'placeholder': 'e.g. Paracetamol', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'strength': forms.TextInput(attrs={'placeholder': 'e.g. 500mg', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'formulation': forms.TextInput(attrs={'placeholder': 'e.g. Tablet', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'indications': forms.Textarea(attrs={'rows': 2, 'placeholder': 'What the medicine is for...', 'class': 'w-full p-4 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'batch_number': forms.TextInput(attrs={'placeholder': 'Batch/Lot Number', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'manufacture_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'quantity': forms.NumberInput(attrs={'placeholder': 'Quantity in Stock', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Price per unit', 'step': '0.01', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'}),
            'medicine_type': forms.Select(attrs={'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all'})
        }

class DoctorProfileUpdateForm(forms.ModelForm):
    password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter new password (optional)',
            'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'
        }),
        help_text="Leave blank to keep current password."
    )

    class Meta:
        model = Doctor
        # Removed 'password' from fields
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 
            'speciality', 'qualification', 'address', 
            'license_number', 'cureentHospital', 'description', 'profile_picture',
            'consulting_time_from', 'consulting_time_to'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last Name', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email Address', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Phone Number', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'speciality': forms.TextInput(attrs={'placeholder': 'Specialty', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'qualification': forms.TextInput(attrs={'placeholder': 'Qualification', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Clinic/Home Address', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'license_number': forms.TextInput(attrs={'placeholder': 'License Number', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'cureentHospital': forms.TextInput(attrs={'placeholder': 'Current Hospital', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Professional Bio', 'class': 'w-full p-4 pl-0 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'profile_picture': forms.FileInput(attrs={'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all'}),
            'consulting_time_from': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all', 'placeholder': 'HH:MM'}),
            'consulting_time_to': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full p-4 pl-12 bg-slate-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500/20 outline-none transition-all', 'placeholder': 'HH:MM'}),
        }

    def save(self, commit=True):
        doctor = super().save(commit=False)
        password = self.cleaned_data.get('password')
        
        # Get the original profile picture from database
        try:
            original_doctor = Doctor.objects.get(pk=doctor.pk) if doctor.pk else None
            original_profile_picture = getattr(original_doctor, 'profile_picture', None) if original_doctor else None
        except:
            original_profile_picture = None
        
        new_profile_picture = self.cleaned_data.get('profile_picture')
        
        print(f"=== PROFILE PICTURE DELETION DEBUG ===")
        print(f"Original profile picture: {bool(original_profile_picture)}")
        print(f"New profile picture: {bool(new_profile_picture)}")
        
        # Always delete old image when profile_picture field is in form data
        # This covers both new uploads and clearing the field
        if 'profile_picture' in self.files or 'profile_picture-clear' in self.data:
            if original_profile_picture:
                try:
                    import os
                    old_image_path = original_profile_picture.path
                    print(f"Attempting to delete old image: {old_image_path}")
                    
                    if os.path.isfile(old_image_path):
                        os.remove(old_image_path)
                        print(f"Successfully deleted old profile picture: {old_image_path}")
                    else:
                        print(f"Old profile picture file not found: {old_image_path}")
                except Exception as e:
                    print(f"Error deleting old profile picture: {e}")
                    # Continue saving even if deletion fails
            else:
                print("No original profile picture to delete")
        else:
            print("Profile picture field not in form data - no deletion needed")
        
        if password:
            doctor.password = password
        
        if commit:
            # Save the doctor instance
            doctor.save()
            
            # Verify the change was saved
            print(f"Doctor profile picture after save: {bool(doctor.profile_picture)}")
            if doctor.profile_picture:
                print(f"New image path: {doctor.profile_picture.path}")
            print("=== END PROFILE PICTURE DELETION DEBUG ===")
                
        return doctor

