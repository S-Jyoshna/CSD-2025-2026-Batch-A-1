# Add verification_status to User (default 'Pending' for backward compatibility with existing rows).
# After registration we set verification_status = 'Pending'; admin approval uses status field (unchanged).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_add_user_registration_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='verification_status',
            field=models.CharField(blank=True, default='Pending', max_length=30),
        ),
    ]
