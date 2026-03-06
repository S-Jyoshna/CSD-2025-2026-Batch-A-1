from django.db import migrations, models

def backfill_transaction_numbers(apps, schema_editor):
    Transaction = apps.get_model('app', 'Transaction')
    next_num = 1
    for tx in Transaction.objects.order_by('id').all():
        if getattr(tx, 'transaction_number', None) is None:
            tx.transaction_number = next_num
            tx.save(update_fields=['transaction_number'])
            next_num += 1
        else:
            next_num = max(next_num, (tx.transaction_number or 0) + 1)

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_loantable_loan_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='transaction_number',
            field=models.PositiveIntegerField(unique=True, null=True, blank=True),
        ),
        migrations.RunPython(backfill_transaction_numbers, migrations.RunPython.noop),
    ]
