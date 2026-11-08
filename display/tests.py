from django.test import TestCase
from django.utils import timezone

from core.models import Counter, Service, Ticket, TicketCall


class DisplayBoardTests(TestCase):
    def setUp(self):
        self.service = Service.objects.create(name='General', prefix='A')
        self.cash = Counter.objects.create(name='Counter 1', display_name='Cash Counter')
        self.blood = Counter.objects.create(name='Counter 2', display_name='Room 1 Blood Collection')
        self.xray = Counter.objects.create(name='Counter 3', display_name='Room 2 X-ray')
        self.physical = Counter.objects.create(name='Counter 4', display_name='Room 3 Physical Examination')
        self.other = Counter.objects.create(name='Counter 5', display_name='Registration')

    def make_call(self, number, counter, status=Ticket.Status.CALLED, served=False):
        ticket = Ticket.objects.create(
            service=self.service,
            ticket_number=number,
            number=int(number.lstrip('A')),
            status=status,
            current_counter=counter,
        )
        return TicketCall.objects.create(ticket=ticket, counter=counter, served=served)

    def board(self):
        response = self.client.get('/display/')
        self.assertEqual(response.status_code, 200)
        return response.context['state']

    def station(self, state, key):
        return next(row for row in state['stations'] if row['key'] == key)

    def test_cash_counter_is_featured_and_stations_show_their_calls(self):
        self.make_call('A001', self.cash)
        self.make_call('A002', self.blood)
        self.make_call('A003', self.xray)
        self.make_call('A004', self.other)

        state = self.board()

        self.assertEqual(state['cash']['ticket_number'], 'A001')
        self.assertTrue(state['cash']['active'])
        self.assertEqual(state['cash']['label'], 'CASH COUNTER')

        self.assertEqual(
            [row['name'] for row in state['stations']],
            ['Blood Collection', 'X-ray', 'Physical Examination'],
        )
        self.assertEqual(
            [row['ticket_number'] for row in state['stations']],
            ['A002', 'A003', '---'],
        )
        self.assertEqual(
            [row['active'] for row in state['stations']],
            [True, True, False],
        )

    def test_rows_never_collapse_when_idle(self):
        state = self.board()

        self.assertEqual(state['cash']['ticket_number'], '---')
        self.assertFalse(state['cash']['active'])
        self.assertEqual(len(state['stations']), 3)
        self.assertEqual(
            [row['ticket_number'] for row in state['stations']],
            ['---', '---', '---'],
        )

    def test_the_same_ticket_can_be_active_at_two_stations(self):
        ticket = Ticket.objects.create(
            service=self.service,
            ticket_number='A001',
            number=1,
            status=Ticket.Status.CALLED,
            current_counter=self.cash,
        )
        TicketCall.objects.create(ticket=ticket, counter=self.cash)
        TicketCall.objects.create(ticket=ticket, counter=self.blood)

        state = self.board()

        self.assertEqual(state['cash']['ticket_number'], 'A001')
        self.assertEqual(self.station(state, 'blood')['ticket_number'], 'A001')

    def test_serving_a_ticket_at_one_station_keeps_it_on_the_other(self):
        ticket = Ticket.objects.create(
            service=self.service,
            ticket_number='A001',
            number=1,
            status=Ticket.Status.COMPLETED,
            current_counter=self.blood,
        )
        TicketCall.objects.create(
            ticket=ticket, counter=self.cash, served=True,
            served_at=timezone.now(), duration_seconds=60,
        )
        TicketCall.objects.create(ticket=ticket, counter=self.blood)

        state = self.board()

        self.assertFalse(state['cash']['active'])
        self.assertEqual(self.station(state, 'blood')['ticket_number'], 'A001')

    def test_latest_call_wins_per_counter(self):
        self.make_call('A001', self.blood)
        self.make_call('A002', self.blood)

        state = self.board()

        self.assertEqual(self.station(state, 'blood')['ticket_number'], 'A002')

    def test_served_and_cancelled_calls_are_hidden(self):
        self.make_call('A001', self.cash)
        self.make_call('A002', self.blood, served=True)
        self.make_call('A003', self.xray, status=Ticket.Status.COMPLETED)
        self.make_call('A004', self.physical, status=Ticket.Status.CANCELLED)

        state = self.board()

        self.assertEqual(state['cash']['ticket_number'], 'A001')
        # A003 was completed at another station but is still open here.
        self.assertEqual(
            [row['ticket_number'] for row in state['stations']],
            ['---', 'A003', '---'],
        )

    def test_calling_the_same_ticket_at_another_counter_keeps_the_old_row(self):
        call = self.make_call('A001', self.blood)
        TicketCall.objects.create(ticket=call.ticket, counter=self.xray)

        state = self.board()

        self.assertEqual(self.station(state, 'blood')['ticket_number'], 'A001')
        self.assertEqual(self.station(state, 'xray')['ticket_number'], 'A001')

    def test_finishing_a_ticket_at_one_counter_keeps_the_other_row(self):
        call = self.make_call('A001', self.blood)
        moved = TicketCall.objects.create(ticket=call.ticket, counter=self.xray)
        # xray finished it; the blood station is still serving the same client.
        moved.served = True
        moved.save(update_fields=['served'])

        state = self.board()

        self.assertEqual(
            [row['ticket_number'] for row in state['stations']],
            ['A001', '---', '---'],
        )

    def test_no_show_calls_are_hidden(self):
        call = self.make_call('A001', self.cash)
        call.no_show = True
        call.served_at = None
        call.save(update_fields=['no_show', 'served_at'])
        call.ticket.status = Ticket.Status.NO_SHOW
        call.ticket.save(update_fields=['status'])

        state = self.board()

        self.assertEqual(state['cash']['ticket_number'], '---')
        self.assertFalse(state['cash']['active'])

    def test_api_returns_cash_and_fixed_stations(self):
        self.make_call('A001', self.cash)
        self.make_call('A002', self.physical)

        payload = self.client.get('/display/api/calls/').json()

        self.assertEqual(payload['cash']['ticket_number'], 'A001')
        self.assertEqual(
            [row['key'] for row in payload['stations']],
            ['blood', 'xray', 'physical'],
        )
        self.assertEqual(
            [row['ticket_number'] for row in payload['stations']],
            ['---', '---', 'A002'],
        )
        self.assertEqual(len(payload['calls']), 2)


class DisplayStationMatchingTests(TestCase):
    """Station rows are matched by counter name, and stay fixed when missing."""

    def setUp(self):
        self.service = Service.objects.create(name='General', prefix='A')

    def make_call(self, number, counter):
        ticket = Ticket.objects.create(
            service=self.service,
            ticket_number=number,
            number=int(number.lstrip('A')),
            status=Ticket.Status.CALLED,
            current_counter=counter,
        )
        return TicketCall.objects.create(ticket=ticket, counter=counter)

    def test_rows_render_without_any_counters(self):
        state = self.client.get('/display/').context['state']

        self.assertEqual(state['cash']['ticket_number'], '---')
        self.assertEqual(len(state['stations']), 3)

    def test_one_counter_is_not_used_for_two_slots(self):
        counter = Counter.objects.create(name='Cash Blood Desk')
        self.make_call('A001', counter)

        state = self.client.get('/display/').context['state']

        self.assertEqual(state['cash']['ticket_number'], 'A001')
        self.assertEqual(
            [row['ticket_number'] for row in state['stations']],
            ['---', '---', '---'],
        )
