from .models import Cart, Notification


def cart_count(request):
    patient_id = request.session.get('patient_id')
    if patient_id:
        count = Cart.objects.filter(patient_id=patient_id).count()
        return {'cart_count': count}
    return {'cart_count': 0}


def pharmacist_notifications(request):
    pharmacist_id = request.session.get('pharmacist_id')
    if pharmacist_id:
        count = Notification.objects.filter(pharmacist_id=pharmacist_id, is_read=False).count()
        return {'pharmacist_notification_count': count}
    return {'pharmacist_notification_count': 0}
