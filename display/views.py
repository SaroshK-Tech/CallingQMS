"""Display board state.

The board has two parts:

* one blue feature card that always belongs to the cash counter;
* three fixed rows (Blood Collection, X-ray, Physical Examination).

Rows never collapse: a row with no active call shows ``---`` in place of the
ticket number, so the layout is stable.
"""
import re

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core import queueing
from core.models import Advertisement, Counter, Ticket, TicketCall

PLACEHOLDER = '---'

CASH_LABEL = 'CASH COUNTER'
CASH_HINTS = ('cash',)

# Right-hand rows, in display order.
STATIONS = (
    {'key': 'blood', 'name': 'Blood Collection', 'hints': ('blood',)},
    {'key': 'xray', 'name': 'X-ray', 'hints': ('x ray', 'xray')},
    {'key': 'physical', 'name': 'Physical Examination', 'hints': ('physical',)},
)


def _normalize(value):
    return re.sub(r'[^a-z0-9]+', ' ', (value or '').lower()).strip()


def _matches(counter, hints):
    label = _normalize(counter.display_name or counter.name)
    return any(hint in label for hint in hints)


def _active_calls():
    """Latest active call for every counter.

    Each counter owns its queue, so a ticket can be active at several stations
    at the same time (cash, blood, x-ray, …).  Only the newest open call per
    counter is kept; served and no-show calls are gone.
    """
    calls = (
        TicketCall.objects
        .filter(
            ticket__created_at__date=timezone.localdate(),
            served=False,
            no_show=False,
            cancelled=False,
        )
        .exclude(ticket__status=Ticket.Status.CANCELLED)
        .select_related('ticket', 'ticket__service', 'counter')
        .order_by('-called_at', '-id')
    )

    latest_per_counter = {}
    for call in calls:
        latest_per_counter.setdefault(call.counter_id, call)

    return list(latest_per_counter.values())


def _serialize(call):
    return {
        'ticket_id': call.ticket_id,
        'ticket_number': call.ticket.ticket_number,
        'counter_id': call.counter_id,
        'counter_name': call.counter.display_name or call.counter.name,
        'service': call.ticket.service.name,
        'called_at': timezone.localtime(call.called_at).strftime('%H:%M:%S'),
    }


def _make_slot(counter, call, extra=None):
    """Board slot for a counter (or a placeholder when no counter is configured)."""
    slot = {
        'ticket_id': None,
        'ticket_number': PLACEHOLDER,
        'counter_id': counter.id if counter else None,
        'active': False,
    }
    if extra:
        slot.update(extra)
    if call is not None:
        slot.update({
            'ticket_id': call.ticket_id,
            'ticket_number': call.ticket.ticket_number,
            'active': True,
            'called_at': timezone.localtime(call.called_at).strftime('%H:%M:%S'),
        })
    return slot


def _pick_counter(counters, hints, used):
    for counter in counters:
        if counter.id in used:
            continue
        if _matches(counter, hints):
            used.add(counter.id)
            return counter
    return None


def board_state():
    """Cash feature card + the three fixed station rows."""
    counters = list(Counter.objects.filter(is_active=True).order_by('id'))
    calls_by_counter = {call.counter_id: call for call in _active_calls()}
    used = set()

    # The admin-flagged main counter wins; the name convention is the fallback.
    main = next((counter for counter in counters if counter.is_main), None)
    if main is not None:
        used.add(main.id)
        cash_counter = main
    else:
        cash_counter = _pick_counter(counters, CASH_HINTS, used)
    cash = _make_slot(
        cash_counter,
        calls_by_counter.get(cash_counter.id) if cash_counter else None,
        {'label': CASH_LABEL},
    )

    stations = []
    for station in STATIONS:
        counter = _pick_counter(counters, station['hints'], used)
        call = calls_by_counter.get(counter.id) if counter else None
        stations.append(_make_slot(counter, call, {
            'key': station['key'],
            'name': station['name'],
        }))

    return {'cash': cash, 'stations': stations, 'calls': [_serialize(c) for c in calls_by_counter.values()]}


def full_display(request):
    return render(request, 'display/full_display.html', {
        'state': board_state(),
        'today': timezone.localdate(),
    })


def api_now_serving(request):
    return JsonResponse(board_state())


def api_counter_now_serving(request, counter_id):
    """Current call for one counter, used by the ESP32/P10 display panel.

    Public on purpose: the panel has no login session and only reads the same
    ticket number that is already shown on the public board.
    """
    counter = get_object_or_404(Counter, id=counter_id, is_active=True)
    call = queueing.active_call(counter)
    ticket = call.ticket if call is not None else None

    return JsonResponse({
        'counter_id': counter.id,
        'counter_name': counter.display_name or counter.name,
        'active': call is not None,
        'ticket_id': ticket.id if ticket else None,
        'ticket_number': ticket.ticket_number if ticket else None,
        'service': ticket.service.name if ticket else None,
        'service_prefix': ticket.service.prefix if ticket else None,
        'called_at': (
            timezone.localtime(call.called_at).strftime('%H:%M:%S')
            if call else None
        ),
        'called_at_iso': (
            timezone.localtime(call.called_at).isoformat()
            if call else None
        ),
        'recall_count': call.recall_count if call else 0,
        'server_time': timezone.localtime().isoformat(),
    })


def api_advertisements(request):
    ads = Advertisement.objects.filter(is_active=True)
    data = [{
        'id': ad.id,
        'title': ad.title,
        'image': ad.image.url if ad.image else None,
        'video': ad.video.url if ad.video else None,
    } for ad in ads]
    return JsonResponse({'advertisements': data})
