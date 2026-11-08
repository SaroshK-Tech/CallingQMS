"""Queue rules shared by the dashboard, WebSocket consumers and APIs.

Two independent rules live here:

* **Categories** (``Service``) are either *usual* and visible at every active
  counter, or *exceptional* and only visible at the counters the admin linked
  to them via ``CounterService``.
* **Every counter owns its queue.**  A ticket is removed from a counter's
  waiting list when *that* counter calls it or finishes it — a call at another
  counter never removes it.  One client can therefore be served at several
  counters (cash, blood, x-ray, …) with one ``TicketCall`` per station, each
  recording its own duration.
* **The main counter (cash) releases usual tickets.**  A usual-category ticket
  stays at the main counter until the client is confirmed with Done & Next;
  only then does it appear in the other counters' waiting lists.  Exceptional
  categories keep their admin routing and are not gated.  If no counter is
  flagged as main, the gate is disabled so the system never deadlocks.

The helpers in this module keep both rules in one place so the JSON API, the
dashboard page, the WebSocket actions and the tests cannot drift apart.
"""
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from core.models import Counter, CounterService, Feedback, Service, Ticket, TicketCall

# Name convention used when no counter is flagged ``is_main`` in admin.
MAIN_NAME_HINTS = ('cash',)


# ---------------------------------------------------------------------------
# Main (cash) counter
# ---------------------------------------------------------------------------
def main_counters():
    """Active counters flagged as main, with a name-based fallback."""
    flagged = Counter.objects.filter(is_active=True, is_main=True)
    if flagged.exists():
        return flagged
    return Counter.objects.filter(is_active=True).filter(
        Q(name__icontains='cash') | Q(display_name__icontains='cash')
    )


def main_counter_ids():
    return list(main_counters().values_list('id', flat=True))


def is_main_counter(counter):
    if counter is None:
        return False
    return main_counters().filter(id=counter.id).exists()


def released_by_main(ticket):
    """True when ``ticket`` does not need the main counter (or already passed it)."""
    main_ids = main_counter_ids()
    if not main_ids or not ticket.service.is_usual:
        return True
    return TicketCall.objects.filter(
        ticket=ticket,
        counter_id__in=main_ids,
        served=True,
        no_show=False,
        cancelled=False,
    ).exists()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def services_for_counter(counter):
    """Active categories that may be called from ``counter``.

    Usual categories are available everywhere; exceptional ones only where the
    admin linked them through ``CounterService``.
    """
    return (
        Service.objects
        .filter(is_active=True)
        .filter(Q(is_usual=True) | Q(counterservice__counter=counter))
        .distinct()
        .order_by('prefix')
    )


def service_allowed(counter, service):
    if counter is None or service is None or not service.is_active:
        return False
    if service.is_usual:
        return True
    return CounterService.objects.filter(counter=counter, service=service).exists()


# ---------------------------------------------------------------------------
# Call queries
# ---------------------------------------------------------------------------
def open_calls():
    """Calls that are still active at their counter.

    A ticket may be active at several counters at once, so the ticket status is
    deliberately not used here: only the call itself decides.
    """
    return TicketCall.objects.filter(served=False, no_show=False, cancelled=False)


def active_call(counter):
    """The client currently at ``counter``, if any."""
    return (
        open_calls()
        .filter(counter=counter, ticket__created_at__date=timezone.localdate())
        .select_related('ticket', 'ticket__service', 'counter')
        .order_by('-called_at', '-id')
        .first()
    )


def waiting_queryset(counter):
    """Today's waiting tickets for ``counter`` — this counter's own queue.

    A ticket leaves *this* queue only when this counter calls it or finishes it;
    what other counters do with the ticket is irrelevant.  No-show tickets come
    back to the queue and sort first so the operator can try them again.
    Usual-category tickets only reach the other counters after the main (cash)
    counter confirmed them with Done & Next.  Cancelled tickets never appear.
    """
    served_here = (
        TicketCall.objects
        .filter(counter=counter, served=True, no_show=False)
        .values('ticket_id')
    )
    open_here = (
        TicketCall.objects
        .filter(counter=counter, served=False, no_show=False, cancelled=False)
        .values('ticket_id')
    )
    no_show_here = Exists(
        TicketCall.objects.filter(
            counter=counter,
            ticket=OuterRef('pk'),
            no_show=True,
        )
    )
    main_ids = main_counter_ids()
    confirmed_at_main = Exists(
        TicketCall.objects.filter(
            ticket=OuterRef('pk'),
            counter_id__in=main_ids,
            served=True,
            no_show=False,
            cancelled=False,
        )
    )

    queryset = (
        Ticket.objects
        .filter(
            service__in=services_for_counter(counter),
            created_at__date=timezone.localdate(),
        )
        .exclude(status=Ticket.Status.CANCELLED)
        .exclude(id__in=served_here)
        .exclude(id__in=open_here)
    )

    # Only the main counter holds usual tickets before confirmation.
    if main_ids and counter.id not in main_ids:
        queryset = queryset.filter(Q(service__is_usual=False) | confirmed_at_main)

    return (
        queryset
        .select_related('service')
        .annotate(no_show_here=no_show_here)
        .order_by('-no_show_here', 'created_at', 'id')
    )


def called_queryset(counter, limit=100):
    """Tickets this counter finished today, newest first."""
    return (
        TicketCall.objects
        .filter(
            counter=counter,
            served=True,
            no_show=False,
            cancelled=False,
            served_at__date=timezone.localdate(),
            ticket__created_at__date=timezone.localdate(),
        )
        .select_related('ticket', 'ticket__service', 'counter')
        .order_by('-served_at', '-id')[:limit]
    )


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------
def _close_call(call, now):
    call.served = True
    call.served_at = now
    call.duration_seconds = max(0, int((now - call.called_at).total_seconds()))
    call.save(update_fields=['served', 'served_at', 'duration_seconds'])
    return call


def start_call(counter, ticket, now=None):
    """Call ``ticket`` at ``counter``.

    Only this counter's own state is touched: another counter serving the same
    ticket keeps its own call and screen.  Calling a different ticket while
    somebody is still at this counter finishes the previous client, so the
    station durations stay accurate without extra operator clicks.

    Returns ``(call, reason)``.  ``reason`` is ``called``, ``already`` or one
    of ``not_allowed`` / ``closed`` / ``not_today`` / ``not_confirmed``.
    """
    now = now or timezone.now()
    if not service_allowed(counter, ticket.service):
        return None, 'not_allowed'
    if ticket.status == Ticket.Status.CANCELLED:
        return None, 'closed'
    if ticket.created_at.date() != timezone.localdate():
        return None, 'not_today'
    if not is_main_counter(counter) and not released_by_main(ticket):
        return None, 'not_confirmed'

    existing = (
        open_calls()
        .filter(counter=counter, ticket=ticket)
        .order_by('-called_at', '-id')
        .first()
    )
    if existing is not None:
        return existing, 'already'

    # Close whoever is currently at this counter; calling a different client
    # completes the previous one.
    current = active_call(counter)
    if current is not None:
        _close_call(current, now)
        current.ticket.status = Ticket.Status.COMPLETED
        current.ticket.completed_at = now
        current.ticket.save(update_fields=['status', 'completed_at'])

    ticket.current_counter = counter
    ticket.called_at = now
    ticket.status = Ticket.Status.CALLED
    ticket.save(update_fields=['current_counter', 'called_at', 'status'])

    call = TicketCall.objects.create(ticket=ticket, counter=counter)
    return call, 'called'


def finish_call(counter, ticket, now=None):
    """Mark this counter's call as completed and record the station duration."""
    now = now or timezone.now()
    call = (
        open_calls()
        .filter(counter=counter, ticket=ticket)
        .order_by('-called_at', '-id')
        .first()
    )
    if call is None:
        return None

    _close_call(call, now)

    ticket.status = Ticket.Status.COMPLETED
    ticket.completed_at = now
    ticket.save(update_fields=['status', 'completed_at'])
    return call


def mark_no_show(counter, ticket, now=None):
    """Return a called client to this counter's queue with a ``No show`` badge.

    The call at ``counter`` is closed as a no-show; the ticket stays available
    here (and anywhere else it was waiting) so it can be called again.
    """
    now = now or timezone.now()
    call = (
        open_calls()
        .filter(counter=counter, ticket=ticket)
        .order_by('-called_at', '-id')
        .first()
    )
    if call is None:
        return None

    call.no_show = True
    call.served = False
    call.served_at = now
    call.duration_seconds = max(0, int((now - call.called_at).total_seconds()))
    call.save(update_fields=['no_show', 'served', 'served_at', 'duration_seconds'])

    still_active = open_calls().filter(ticket=ticket).exclude(id=call.id).exists()
    ticket.status = Ticket.Status.NO_SHOW
    ticket.no_show_count += 1
    if not still_active:
        ticket.current_counter = None
    ticket.save(update_fields=['status', 'no_show_count', 'current_counter'])
    return call


def terminate_ticket(counter, ticket, now=None):
    """Terminate (cancel) a client from the main counter.

    The ticket is cancelled and removed from every queue and display board; the
    station record is closed so the time spent is still auditable.  Only the
    main counter may do this, and a cancelled ticket stays cancelled.
    """
    now = now or timezone.now()
    if not is_main_counter(counter):
        return None
    if ticket.status == Ticket.Status.CANCELLED:
        return None

    for call in open_calls().filter(ticket=ticket):
        call.cancelled = True
        call.served = True
        call.served_at = now
        call.duration_seconds = max(0, int((now - call.called_at).total_seconds()))
        call.save(update_fields=[
            'cancelled', 'served', 'served_at', 'duration_seconds',
        ])

    ticket.status = Ticket.Status.CANCELLED
    ticket.completed_at = now
    ticket.current_counter = None
    ticket.save(update_fields=['status', 'completed_at', 'current_counter'])
    return ticket


def recall_call(counter, ticket):
    """Re-announce the active client without resetting the station timer."""
    call = (
        open_calls()
        .filter(counter=counter, ticket=ticket)
        .order_by('-called_at', '-id')
        .first()
    )
    if call is None:
        return None

    call.recalled = True
    call.recall_count += 1
    call.save(update_fields=['recalled', 'recall_count'])
    return call


def next_ticket(counter, now=None):
    """Call the first waiting ticket (no-show tickets first)."""
    ticket = waiting_queryset(counter).first()
    if ticket is None:
        return None, None
    return start_call(counter, ticket, now=now)


def done_and_next(counter, ticket, now=None):
    """Finish ``ticket`` and immediately call the next waiting client."""
    now = now or timezone.now()
    finished = finish_call(counter, ticket, now=now)
    if finished is None:
        return None, None
    called, _reason = next_ticket(counter, now=now)
    return finished, called


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------
def format_duration(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


def call_payload(call, event_type='ticket_called'):
    ticket = call.ticket
    payload = {
        'type': event_type,
        'ticket_id': ticket.id,
        'ticket_number': ticket.ticket_number,
        'counter_id': call.counter_id,
        'counter_name': call.counter.display_name or call.counter.name,
        'service': ticket.service.name,
        'service_id': ticket.service_id,
        'called_at': timezone.localtime(call.called_at).strftime('%H:%M:%S'),
        'called_at_iso': timezone.localtime(call.called_at).isoformat(),
    }
    if event_type in ('ticket_served', 'ticket_cancelled'):
        payload.update({
            'served_at': timezone.localtime(call.served_at).strftime('%H:%M:%S'),
            'duration_seconds': call.duration_seconds,
            'duration': format_duration(call.duration_seconds),
        })
    if event_type == 'ticket_no_show':
        payload.update({
            'no_show_count': ticket.no_show_count,
        })
    return payload


def build_dashboard_state(counter):
    """Everything the counter control panel needs, as plain JSON data."""
    now = timezone.now()
    active = active_call(counter)
    waiting = waiting_queryset(counter)
    called = called_queryset(counter)

    return {
        'server_time': timezone.localtime(now).isoformat(),
        'is_main': is_main_counter(counter),
        'counter': {
            'id': counter.id,
            'name': counter.display_name or counter.name,
        },
        'active': _active_payload(active),
        'waiting': [
            {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'service': ticket.service.name,
                'service_prefix': ticket.service.prefix,
                'dispensed_at': timezone.localtime(ticket.created_at).isoformat(),
                'dispensed_time': timezone.localtime(ticket.created_at).strftime('%I:%M %p'),
                'no_show': bool(getattr(ticket, 'no_show_here', False)),
                'no_show_count': ticket.no_show_count,
            }
            for ticket in waiting
        ],
        'called': [
            {
                'ticket_id': call.ticket_id,
                'ticket_number': call.ticket.ticket_number,
                'service': call.ticket.service.name,
                'served_at': timezone.localtime(call.served_at).isoformat(),
                'served_time': timezone.localtime(call.served_at).strftime('%I:%M %p'),
                'duration_seconds': call.duration_seconds,
                'duration': format_duration(call.duration_seconds),
            }
            for call in called
        ],
    }


def _active_payload(call):
    if call is None:
        return None
    return {
        'ticket_id': call.ticket_id,
        'ticket_number': call.ticket.ticket_number,
        'service': call.ticket.service.name,
        'called_at': timezone.localtime(call.called_at).isoformat(),
        'called_time': timezone.localtime(call.called_at).strftime('%I:%M %p'),
        'recall_count': call.recall_count,
        'feedback': Feedback.objects.filter(ticket=call.ticket).exists(),
    }
