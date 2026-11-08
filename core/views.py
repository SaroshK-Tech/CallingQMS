from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.models import Feedback, Ticket


def public_feedback(request, ticket_number):
    """Public per-ticket feedback page.

    The URL is printed on the kiosk receipt and shown in the ticket popup, so a
    client can rate the visit from a phone even after leaving the counter.
    """
    ticket = get_object_or_404(
        Ticket.objects.select_related('service', 'current_counter'),
        ticket_number=ticket_number,
    )
    existing = Feedback.objects.filter(ticket=ticket).first()
    error = None

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', ''))
        except (TypeError, ValueError):
            rating = 0

        if rating < 1 or rating > 5:
            error = 'Please choose a rating between 1 and 5 stars.'
        else:
            last_call = (
                ticket.calls.filter(served=True).select_related('counter')
                .order_by('-served_at', '-id').first()
                or ticket.calls.select_related('counter').order_by('-called_at', '-id').first()
            )
            counter = (
                (existing.counter if existing and existing.counter else None)
                or ticket.current_counter
                or (last_call.counter if last_call else None)
            )
            Feedback.objects.update_or_create(
                ticket=ticket,
                defaults={
                    'counter': counter,
                    'rating': rating,
                    'comment': (request.POST.get('comment') or '').strip(),
                    'source': Feedback.Source.PUBLIC,
                },
            )
            return redirect(
                reverse('public_feedback', args=[ticket.ticket_number]) + '?done=1'
            )

    return render(request, 'feedback/public_feedback.html', {
        'ticket': ticket,
        'feedback': existing,
        'done': request.GET.get('done') == '1',
        'error': error,
        'rating_values': range(1, 6),
    })
