import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket for counter user dashboards - receives ticket updates"""

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
        data = json.loads(text_data)
        action = data.get('action')
        update_data = None
        room = f'dashboard_{self.counter_id}'

        if action == 'call_ticket':
            update_data, announce_to = await self.call_ticket(data)
        elif action == 'recall_ticket':
            update_data, announce_to = await self.recall_ticket(data)
        elif action == 'done_ticket':
            update_data, announce_to = await self.done_ticket(data)
        elif action == 'next_ticket':
            update_data, announce_to = await self.next_ticket(data)
        elif action == 'prev_ticket':
            update_data, announce_to = await self.prev_ticket(data)
        else:
            return

        if not update_data:
            return

        # Announcement only for a fresh call
        if announce_to == 'all':
            await self.channel_layer.group_send(
                'display_board',
                {'type': 'new_call', 'data': update_data}
            )

        await self.channel_layer.group_send(
            room,
            {'type': 'ticket_update', 'data': update_data}
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

    @database_sync_to_async
    def _call_ticket_db(self, data):
        from core.models import Ticket, TicketCall, Counter

        ticket_id = data.get('ticket_id')
        counter_id = data.get('counter_id', self.counter_id)

        try:
            ticket = Ticket.objects.get(id=ticket_id)
            counter = Counter.objects.get(id=counter_id)
        except (Ticket.DoesNotExist, Counter.DoesNotExist):
            return None

        ticket.current_counter = counter
        ticket.called_at = timezone.now()
        ticket.save()

        TicketCall.objects.create(ticket=ticket, counter=counter)

        return {
            'type': 'ticket_called',
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'counter_name': counter.display_name or counter.name,
            'counter_id': counter.id,
            'service': ticket.service.name,
            'called_at': ticket.called_at.strftime('%H:%M:%S'),
        }

    async def call_ticket(self, data):
        result = await self._call_ticket_db(data)
        if result:
            await self._trigger_audio(result['ticket_number'], result['counter_name'])
            return result, 'all'
        return None, None

    @database_sync_to_async
    def _recall_ticket_db(self, data):
        from core.models import Ticket, TicketCall, Counter

        ticket_id = data.get('ticket_id')
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            counter = Counter.objects.get(id=self.counter_id)
        except (Ticket.DoesNotExist, Counter.DoesNotExist):
            return None

        ticket.called_at = timezone.now()
        ticket.save()

        TicketCall.objects.create(ticket=ticket, counter=counter, recalled=True)

        return {
            'type': 'ticket_recalled',
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'counter_name': counter.display_name or counter.name,
            'counter_id': counter.id,
            'called_at': ticket.called_at.strftime('%H:%M:%S'),
        }

    async def recall_ticket(self, data):
        result = await self._recall_ticket_db(data)
        if result:
            await self._trigger_audio(result['ticket_number'], result['counter_name'])
            return result, 'all'
        return None, None

    @database_sync_to_async
    def _done_ticket_db(self, data):
        from core.models import Ticket, TicketCall, Counter

        ticket_id = data.get('ticket_id')
        try:
            counter = Counter.objects.get(id=self.counter_id)
        except Counter.DoesNotExist:
            return None

        ticket = Ticket.objects.filter(id=ticket_id).first()
        if not ticket:
            return None

        # Mark this counter's latest call for the ticket as served
        call = TicketCall.objects.filter(
            ticket=ticket, counter=counter
        ).order_by('-called_at').first()

        if call is None:
            call = TicketCall.objects.create(ticket=ticket, counter=counter)

        call.served = True
        call.called_at = timezone.now()
        call.save()

        return {
            'type': 'ticket_served',
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'counter_id': counter.id,
            'counter_name': counter.display_name or counter.name,
            'served_at': call.called_at.strftime('%H:%M:%S'),
        }

    async def done_ticket(self, data):
        result = await self._done_ticket_db(data)
        if result:
            return result, 'self'
        return None, None

    @database_sync_to_async
    def _next_ticket_db(self, data):
        from core.models import Ticket

        counter_id = data.get('counter_id', self.counter_id)
        counter = self._get_counter(counter_id)
        if not counter:
            return None

        served_ids = (
            Ticket.objects.filter(calls__counter=counter, calls__served=True)
            .values_list('id', flat=True)
        )

        waiting = (
            Ticket.objects
            .filter(service__in=counter.services.all())
            .exclude(id__in=served_ids)
            .exclude(status=Ticket.Status.COMPLETED)
            .exclude(status=Ticket.Status.CANCELLED)
            .order_by('created_at')
            .first()
        )

        if not waiting:
            return None

        from core.models import TicketCall
        waiting.current_counter = counter
        waiting.called_at = timezone.now()
        waiting.save()
        TicketCall.objects.create(ticket=waiting, counter=counter)

        return {
            'type': 'ticket_called',
            'ticket_id': waiting.id,
            'ticket_number': waiting.ticket_number,
            'counter_name': counter.display_name or counter.name,
            'counter_id': counter.id,
            'service': waiting.service.name,
            'called_at': waiting.called_at.strftime('%H:%M:%S'),
        }

    async def next_ticket(self, data):
        result = await self._next_ticket_db(data)
        if result:
            await self._trigger_audio(result['ticket_number'], result['counter_name'])
            return result, 'all'
        return None, None

    @database_sync_to_async
    def _prev_ticket_db(self, data):
        from core.models import TicketCall, Counter

        try:
            counter = Counter.objects.get(id=self.counter_id)
        except Counter.DoesNotExist:
            return None

        last_call = TicketCall.objects.filter(
            counter=counter, served=False
        ).select_related('ticket').order_by('-called_at').first()

        if not last_call:
            return None

        ticket = last_call.ticket
        last_call.called_at = timezone.now()
        last_call.save()

        return {
            'type': 'ticket_recalled',
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'counter_name': counter.display_name or counter.name,
            'counter_id': counter.id,
            'called_at': timezone.now().strftime('%H:%M:%S'),
        }

    async def prev_ticket(self, data):
        result = await self._prev_ticket_db(data)
        if result:
            return result, 'all'
        return None, None

    @staticmethod
    def _get_counter(counter_id):
        from core.models import Counter
        try:
            return Counter.objects.get(id=counter_id)
        except Counter.DoesNotExist:
            return None


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

    async def new_call(self, event):
        data = event['data']
        if str(data.get('counter_id')) == str(self.counter_id):
            await self.send(text_data=json.dumps(data))

    async def ticket_update(self, event):
        await self.send(text_data=json.dumps(event['data']))
