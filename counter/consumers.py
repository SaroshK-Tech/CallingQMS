import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from core import queueing


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket for counter user dashboards.

    Every mutation is written through :mod:`core.queueing` and then broadcast to
    the display board and to *all* dashboards.  The dashboard that triggered the
    action also receives the event, but it simply refetches its state, so there
    is no risk of optimistic UI drift.
    """

    async def connect(self):
        self.counter_id = self.scope['url_route']['kwargs'].get('counter_id')
        self.group_name = f'dashboard_{self.counter_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add('all_dashboards', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.channel_layer.group_discard('all_dashboards', self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get('action')
        payloads = []
        announcements = []

        if action == 'call_ticket':
            payloads, announcements = await self.call_ticket(data)
        elif action == 'recall_ticket':
            payloads, announcements = await self.recall_ticket(data)
        elif action == 'done_ticket':
            payloads, announcements = await self.done_ticket(data)
        elif action == 'done_next_ticket':
            payloads, announcements = await self.done_next_ticket(data)
        elif action == 'no_show_ticket':
            payloads, announcements = await self.no_show_ticket(data)
        elif action == 'terminate_ticket':
            payloads, announcements = await self.terminate_ticket(data)
        elif action == 'next_ticket':
            payloads, announcements = await self.next_ticket(data)
        else:
            return

        for payload in payloads:
            await self._broadcast(payload)

        for ticket_number, counter_name in announcements:
            await self._trigger_audio(ticket_number, counter_name)

    async def _broadcast(self, payload):
        await self.channel_layer.group_send(
            'display_board',
            {
                'type': 'new_call' if payload['type'] == 'ticket_called' else 'ticket_update',
                'data': payload,
            },
        )
        await self.channel_layer.group_send(
            'all_dashboards',
            {'type': 'ticket_update', 'data': payload},
        )

    async def ticket_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def ticket_created(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def display_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def _trigger_audio(self, ticket_number, counter_name):
        # Fire-and-forget server-side playback (runs in a thread)
        import asyncio

        from core.audio_player import announce

        asyncio.get_running_loop().run_in_executor(
            None, announce, ticket_number, counter_name
        )

    # -- actions ---------------------------------------------------------
    async def call_ticket(self, data):
        payload, announce = await self._call_ticket_db(data)
        if payload is None:
            return [], []
        return [payload], [announce] if announce else []

    async def recall_ticket(self, data):
        payload = await self._recall_ticket_db(data)
        if payload is None:
            return [], []
        return [payload], [(payload['ticket_number'], payload['counter_name'])]

    async def done_ticket(self, data):
        payload = await self._done_ticket_db(data)
        return ([payload], []) if payload else ([], [])

    async def done_next_ticket(self, data):
        payloads, announce = await self._done_next_db(data)
        return payloads, [announce] if announce else []

    async def no_show_ticket(self, data):
        payload = await self._no_show_db(data)
        return ([payload], []) if payload else ([], [])

    async def terminate_ticket(self, data):
        payload = await self._terminate_db(data)
        return ([payload], []) if payload else ([], [])

    async def next_ticket(self, data):
        payload = await self._next_ticket_db(data)
        if payload is None:
            return [], []
        return [payload], [(payload['ticket_number'], payload['counter_name'])]

    # -- database helpers ------------------------------------------------
    @database_sync_to_async
    def _counter(self, counter_id):
        from core.models import Counter

        return Counter.objects.filter(id=counter_id, is_active=True).first()

    @database_sync_to_async
    def _ticket(self, ticket_id):
        from core.models import Ticket

        return (
            Ticket.objects
            .select_related('service')
            .filter(id=ticket_id)
            .first()
        )

    async def _call_ticket_db(self, data):
        counter = await self._counter(data.get('counter_id', self.counter_id))
        ticket = await self._ticket(data.get('ticket_id'))
        if counter is None or ticket is None:
            return None, None

        payload = await call_ticket_sync(counter, ticket)
        if payload is None:
            return None, None
        if payload['type'] == 'ticket_called':
            return payload, (payload['ticket_number'], payload['counter_name'])
        return payload, None

    async def _recall_ticket_db(self, data):
        counter = await self._counter(self.counter_id)
        ticket = await self._ticket(data.get('ticket_id'))
        if counter is None or ticket is None:
            return None
        return await recall_ticket_sync(counter, ticket)

    async def _done_ticket_db(self, data):
        counter = await self._counter(self.counter_id)
        ticket = await self._ticket(data.get('ticket_id'))
        if counter is None or ticket is None:
            return None
        return await finish_ticket_sync(counter, ticket)

    async def _done_next_db(self, data):
        counter = await self._counter(self.counter_id)
        ticket = await self._ticket(data.get('ticket_id'))
        if counter is None or ticket is None:
            return [], None
        return await done_next_sync(counter, ticket)

    async def _no_show_db(self, data):
        counter = await self._counter(self.counter_id)
        ticket = await self._ticket(data.get('ticket_id'))
        if counter is None or ticket is None:
            return None
        return await no_show_sync(counter, ticket)

    async def _terminate_db(self, data):
        counter = await self._counter(self.counter_id)
        ticket = await self._ticket(data.get('ticket_id'))
        if counter is None or ticket is None:
            return None
        return await terminate_sync(counter, ticket)

    async def _next_ticket_db(self, data):
        counter = await self._counter(data.get('counter_id', self.counter_id))
        if counter is None:
            return None
        payload = await next_ticket_sync(counter)
        return payload


@database_sync_to_async
def call_ticket_sync(counter, ticket):
    call, reason = queueing.start_call(counter, ticket)
    if call is None:
        return None
    if reason == 'already':
        return queueing.call_payload(call, 'ticket_recalled')
    return queueing.call_payload(call, 'ticket_called')


@database_sync_to_async
def recall_ticket_sync(counter, ticket):
    call = queueing.recall_call(counter, ticket)
    if call is None:
        return None
    return queueing.call_payload(call, 'ticket_recalled')


@database_sync_to_async
def finish_ticket_sync(counter, ticket):
    call = queueing.finish_call(counter, ticket)
    if call is None:
        return None
    return queueing.call_payload(call, 'ticket_served')


@database_sync_to_async
def done_next_sync(counter, ticket):
    finished, called = queueing.done_and_next(counter, ticket)
    payloads = []
    if finished is not None:
        payloads.append(queueing.call_payload(finished, 'ticket_served'))
    announce = None
    if called is not None:
        payload = queueing.call_payload(called, 'ticket_called')
        payloads.append(payload)
        announce = (payload['ticket_number'], payload['counter_name'])
    return payloads, announce


@database_sync_to_async
def no_show_sync(counter, ticket):
    call = queueing.mark_no_show(counter, ticket)
    if call is None:
        return None
    return queueing.call_payload(call, 'ticket_no_show')


@database_sync_to_async
def terminate_sync(counter, ticket):
    call = (
        queueing.open_calls()
        .filter(counter=counter, ticket=ticket)
        .order_by('-called_at', '-id')
        .first()
    )
    terminated = queueing.terminate_ticket(counter, ticket)
    if terminated is None:
        return None
    if call is not None:
        call.refresh_from_db()
        return queueing.call_payload(call, 'ticket_cancelled')
    return {
        'type': 'ticket_cancelled',
        'ticket_id': terminated.id,
        'ticket_number': terminated.ticket_number,
        'counter_id': counter.id,
        'counter_name': counter.display_name or counter.name,
        'service': terminated.service.name,
    }


@database_sync_to_async
def next_ticket_sync(counter):
    call, _reason = queueing.next_ticket(counter)
    if call is None:
        return None
    return queueing.call_payload(call, 'ticket_called')


class DisplayConsumer(AsyncWebsocketConsumer):
    """WebSocket for the full display board"""

    async def connect(self):
        self.group_name = 'display_board'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def new_call(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def ticket_update(self, event):
        await self.send(text_data=json.dumps(event['data']))


class SingleCounterConsumer(AsyncWebsocketConsumer):
    """WebSocket for single counter display"""

    async def connect(self):
        self.counter_id = self.scope['url_route']['kwargs'].get('counter_id')
        self.group_name = f'counter_display_{self.counter_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        # Also listen to display_board for calls to this counter
        await self.channel_layer.group_add('display_board', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.channel_layer.group_discard('display_board', self.channel_name)

    def _is_mine(self, data):
        return str(data.get('counter_id')) == str(self.counter_id)

    async def new_call(self, event):
        data = event['data']
        if self._is_mine(data):
            await self.send(text_data=json.dumps(data))

    async def ticket_update(self, event):
        data = event['data']
        if self._is_mine(data):
            await self.send(text_data=json.dumps(data))
