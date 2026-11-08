from django.db import migrations


def mark_a_usual(apps, schema_editor):
    """Existing category A (General) becomes the usual queue."""
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(prefix='A').update(is_usual=True)


def unmark_a_usual(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(prefix='A').update(is_usual=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_service_is_usual_ticket_no_show_count_and_more'),
    ]

    operations = [
        migrations.RunPython(mark_a_usual, unmark_a_usual),
    ]
