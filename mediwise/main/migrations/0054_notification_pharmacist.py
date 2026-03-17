from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0053_order_scheduled_delivery_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='patient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='main.patient'),
        ),
        migrations.AddField(
            model_name='notification',
            name='pharmacist',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='main.pharmacist'),
        ),
    ]
