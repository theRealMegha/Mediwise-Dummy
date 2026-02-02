from .models import Cart

def cart_count(request):
    patient_id = request.session.get('patient_id')
    if patient_id:
        count = Cart.objects.filter(patient_id=patient_id).count()
        return {'cart_count': count}
    return {'cart_count': 0}
