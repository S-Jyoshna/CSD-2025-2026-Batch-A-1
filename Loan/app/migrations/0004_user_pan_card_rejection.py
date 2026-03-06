# KYC-style verification: PAN card document upload path and rejection reason (admin verification).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_user_verification_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='pan_card_document',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='user',
            name='rejection_reason',
            field=models.TextField(blank=True, default=''),
        ),
    ]
