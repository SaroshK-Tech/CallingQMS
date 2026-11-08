import json
from django.shortcuts import render
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.models import Service, Ticket


def kiosk_screen(request):
    services = Service.objects.filter(is_active=True)
    return render(request, 'kiosk/kiosk.html', {
        'services': services,
    })


@csrf_exempt
def generate_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Auto-select first service if not provided
    if not service_id:
        service = Service.objects.filter(is_active=True).first()
        if not service:
            return JsonResponse({'error': 'No active service found'}, status=404)
    else:
        try:
            service = Service.objects.get(id=service_id, is_active=True)
        except Service.DoesNotExist:
            return JsonResponse({'error': 'Service not found'}, status=404)

    ticket = Ticket(service=service)
    ticket.save()

    # Notify all counter dashboards in real time so waiting lists update live
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(
            'all_dashboards',
            {
                'type': 'ticket_created',
                'data': {
                    'type': 'ticket_created',
                    'ticket_id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'service': service.name,
                    'service_id': service.id,
                    'created_at': timezone.localtime(ticket.created_at).strftime('%H:%M:%S'),
                },
            }
        )

    return JsonResponse({
        'ticket_number': ticket.ticket_number,
        'service': service.name,
        'created_at': timezone.localtime(ticket.created_at).strftime('%Y-%m-%d %H:%M:%S'),
        'feedback_url': request.build_absolute_uri(
            reverse('public_feedback', args=[ticket.ticket_number])
        ),
    })
