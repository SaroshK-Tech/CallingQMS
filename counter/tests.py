import unittest
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import path
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from core.models import Counter, Service, Ticket
from counter.consumers import DashboardConsumer, SingleCounterConsumer, DisplayConsumer


class BroadcastTest(TransactionTestCase):
    APP = URLRouter([
        path('ws/dashboard/<int:counter_id>/', DashboardConsumer.as_asgi()),
        path('ws/counter-display/<int:counter_id>/', SingleCounterConsumer.as_asgi()),
        path('ws/display/', DisplayConsumer.as_asgi()),
    ])

    def setUp(self):
        self.svc = Service.objects.create(name='General', prefix='A')
        self.c1 = Counter.objects.create(name='Counter 1', display_name='Counter 1')
        self.c1.services.add(self.svc)
        self.ticket = Ticket.objects.create(service=self.svc, number=1)

    async def test_display_board_and_counter_display_get_calls(self):
        disp = WebsocketCommunicator(self.APP, '/ws/display/')
        single = WebsocketCommunicator(self.APP, f'/ws/counter-display/{self.c1.id}/')
        dash = WebsocketCommunicator(self.APP, f'/ws/dashboard/{self.c1.id}/')
        connected_d, connected_s, connected_dash = await disp.connect(), await single.connect(), await dash.connect()
        self.assertTrue(connected_d)
        self.assertTrue(connected_s)
        self.assertTrue(connected_dash)

        await dash.send_json_to({'action': 'call_ticket', 'ticket_id': self.ticket.id})

        msg_disp = await disp.receive_json_from(timeout=3)
        msg_single = await single.receive_json_from(timeout=3)
        msg_dash = await dash.receive_json_from(timeout=3)

        for name, msg in [('display', msg_disp), ('counter-display', msg_single), ('dashboard', msg_dash)]:
            self.assertEqual(msg['type'], 'ticket_called', name)
            self.assertEqual(msg['ticket_number'], 'A001', name)

        await disp.disconnect()
        await single.disconnect()
        await dash.disconnect()