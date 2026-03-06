from django.db import migrations, models

def backfill_loan_numbers(apps, schema_editor):
    Loantable = apps.get_model('app', 'Loantable')
    # Assign sequential loan_number starting from 1 for rows missing it.
    # Use stable ordering by primary key id.
    next_num = 1
    for loan in Loantable.objects.order_by('id').all():
        if getattr(loan, 'loan_number', None) is None:
            loan.loan_number = next_num
            loan.save(update_fields=['loan_number'])
            next_num += 1
        else:
            # Ensure uniqueness and monotonicity if existing values are present
            next_num = max(next_num, (loan.loan_number or 0) + 1)

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_loantable_closed_at_loantable_paid_installments_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='loantable',
            name='loan_number',
            field=models.PositiveIntegerField(unique=True, null=True, blank=True),
        ),
        migrations.RunPython(backfill_loan_numbers, migrations.RunPython.noop),
    ]
