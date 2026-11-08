from django.db import migrations
from django.db.models import Q


def mark_cash_main(apps, schema_editor):
    """Existing 'cash' counter becomes the main counter after the upgrade."""
    Counter = apps.get_model('core', 'Counter')
    cash = (
        Counter.objects
        .filter(Q(name__icontains='cash') | Q(display_name__icontains='cash'))
        .order_by('id')
        .first()
    )
    if cash is not None:
        cash.is_main = True
        cash.save(update_fields=['is_main'])


def unmark_cash_main(apps, schema_editor):
    Counter = apps.get_model('core', 'Counter')
    Counter.objects.update(is_main=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_counter_is_main_ticketcall_cancelled'),
    ]

    operations = [
        migrations.RunPython(mark_cash_main, unmark_cash_main),
    ]
