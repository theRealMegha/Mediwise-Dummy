from django.contrib import admin
from .models import Users, Patient, MediAdmin, Pharmacist, Doctor,AuditLog,Medicine


# Register your models here.

admin.site.register(Users)
admin.site.register(Patient)
admin.site.register(MediAdmin)
admin.site.register(Pharmacist)
admin.site.register(Doctor)
admin.site.register(AuditLog)
admin.site.register(Medicine)


