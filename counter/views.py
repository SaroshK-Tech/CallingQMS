import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from core import queueing
from core.models import Counter, Feedback, Ticket, TicketCall


def _profile_counter(request):
    profile = getattr(request.user, 'counter_profile', None)
    return profile.counter if profile else None


@login_required
def counter_dashboard(request):
    counter = _profile_counter(request)
    if not counter:
        return render(request, 'counter/no_counter.html')

    return render(request, 'counter/dashboard.html', {
        'counter': counter,
        'services': queueing.services_for_counter(counter),
        'state': queueing.build_dashboard_state(counter),
    })


@login_required
@require_GET
def dashboard_state(request):
    counter = _profile_counter(request)
    if not counter:
        return JsonResponse({'error': 'No counter assigned'}, status=403)
    return JsonResponse(queueing.build_dashboard_state(counter))


@login_required
@require_POST
def submit_feedback(request):
    counter = _profile_counter(request)
    if not counter:
        return JsonResponse({'error': 'No counter assigned'}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    ticket = get_object_or_404(Ticket, id=data.get('ticket_id'))
    if not TicketCall.objects.filter(ticket=ticket, counter=counter).exists():
        return JsonResponse({'error': 'Ticket was not called at this counter'}, status=403)

    try:
        rating = int(data.get('rating'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Rating must be between 1 and 5'}, status=400)
    if rating < 1 or rating > 5:
        return JsonResponse({'error': 'Rating must be between 1 and 5'}, status=400)

    feedback, created = Feedback.objects.update_or_create(
        ticket=ticket,
        defaults={
            'counter': counter,
            'rating': rating,
            'comment': (data.get('comment') or '').strip(),
            'source': Feedback.Source.COUNTER,
        },
    )
    return JsonResponse({
        'ok': True,
        'created': created,
        'feedback_id': feedback.id,
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
