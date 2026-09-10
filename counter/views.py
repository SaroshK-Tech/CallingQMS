from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from core.models import Counter, Ticket, TicketCall


@login_required
def counter_dashboard(request):
    profile = getattr(request.user, 'counter_profile', None)
    if not profile:
        return render(request, 'counter/no_counter.html')
    
    counter = profile.counter
    services = counter.services.all()

    # Tickets not yet finished (Done) by THIS counter stay in its list
    served_ids = TicketCall.objects.filter(
        counter=counter, served=True
    ).values_list('ticket_id', flat=True)

    waiting_tickets = Ticket.objects.filter(
        service__in=services
    ).exclude(
        id__in=served_ids
    ).exclude(
        status__in=[Ticket.Status.COMPLETED, Ticket.Status.CANCELLED]
    ).select_related('service').order_by('created_at')

    currently_serving = Ticket.objects.filter(
        calls__counter=counter,
        calls__served=False,
    ).exclude(
        status__in=[Ticket.Status.COMPLETED, Ticket.Status.CANCELLED]
    ).select_related('service').order_by('-called_at').first()

    served_today = Ticket.objects.filter(
        calls__counter=counter,
        calls__served=True,
        calls__called_at__date=timezone.localdate()
    ).select_related('service').order_by('-called_at')[:20]
    
    return render(request, 'counter/dashboard.html', {
        'counter': counter,
        'services': services,
        'service_ids': list(services.values_list('id', flat=True)),
        'waiting_tickets': waiting_tickets,
        'currently_serving': currently_serving,
        'recent_completed': served_today,
    })


@login_required
def counter_display(request, counter_id):
    counter = get_object_or_404(Counter, id=counter_id)
    return render(request, 'counter/counter_display.html', {'counter': counter})


@login_required
def api_ticket_status(request, ticket_id):
    try:
        ticket = Ticket.objects.select_related('service', 'current_counter').get(id=ticket_id)
        return JsonResponse({
            'ticket_number': ticket.ticket_number,
            'status': ticket.status,
            'service': ticket.service.name,
            'counter': ticket.current_counter.display_name if ticket.current_counter else None,
        })
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
