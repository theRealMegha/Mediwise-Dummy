from django import template
from datetime import date

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Custom template filter to get dictionary values by key
    Usage: {{ my_dict|get_item:key }}
    """
    try:
        return dictionary.get(str(key), '')
    except (TypeError, AttributeError):
        return ''

@register.filter
def in_dict(dictionary, key):
    """
    Custom template filter to check if key exists in dictionary
    Usage: {{ my_dict|in_dict:key }}
    """
    try:
        return str(key) in dictionary
    except (TypeError, AttributeError):
        return False

@register.filter
def get_prescribing_doctor(prescriptions, medicine_info):
    """
    Custom template filter to get the doctor who prescribed a specific medicine
    Usage: {{ patient_prescriptions|get_prescribing_doctor:medicine.generic_name }}
    """
    from ..models import Prescription, PrescriptionMedicine
    
    for prescription in prescriptions:
        # Check if any medicine in this prescription matches the medicine_info
        for medicine in prescription.medicines.all():
            if (medicine.drug_name_generic == medicine_info or 
                medicine.drug_name_brand == medicine_info):
                return f"Dr. {prescription.doctor.first_name} {prescription.doctor.last_name}"
    return "Unknown Doctor"

@register.filter
def filter_rx_medicines(cart_items):
    """
    Custom template filter to filter cart items that require prescriptions
    Usage: {{ cart_items|filter_rx_medicines }}
    """
    # Import here to avoid circular imports
    from ..models import Medicine
    
    rx_items = []
    for item in cart_items:
        if hasattr(item, 'medicine') and item.medicine.medicine_type == 'Rx':
            rx_items.append(item)
    return rx_items

@register.filter
def filter_not_from_prescription(cart_items):
    """
    Custom template filter to filter cart items that were NOT added from a prescription
    Usage: {{ cart_items|filter_not_from_prescription }}
    """
    non_prescription_items = []
    for item in cart_items:
        # Check if the item was not added from a prescription
        if not getattr(item, 'added_from_prescription', False):
            non_prescription_items.append(item)
    return non_prescription_items

@register.filter
def make_list(value):
    """
    Custom template filter to convert a string to a list of characters
    Usage: {{ 'SMTWTFS'|make_list }}
    """
    return list(value)

@register.filter
def age(date_of_birth):
    """
    Custom template filter to calculate age from date of birth
    Usage: {{ patient.date_of_birth|age }}
    """
    if not date_of_birth:
        return 'N/A'
    
    today = date.today()
    age_years = today.year - date_of_birth.year
    
    # Adjust age if birthday hasn't occurred yet this year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age_years -= 1
    
    return age_years