import json
from datetime import timedelta

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.urls import path
from django.utils import timezone

from core.models import (
    Counter,
    CounterService,
    CounterUser,
    Feedback,
    Service,
    Ticket,
    TicketCall,
)
from core import queueing
from counter.consumers import DashboardConsumer, DisplayConsumer, SingleCounterConsumer


class QueueTestCase(TestCase):
    def setUp(self):
        self.usual = Service.objects.create(name='General', prefix='A', is_usual=True)
        self.exceptional = Service.objects.create(name='VIP', prefix='B')
        self.c1 = Counter.objects.create(name='Counter 1', display_name='Counter 1')
        self.c2 = Counter.objects.create(name='Counter 2', display_name='Counter 2')
        CounterService.objects.create(counter=self.c1, service=self.exceptional)
        self.c1.services.add(self.usual)

    def ticket(self, service, number=1):
        return Ticket.objects.create(service=service, number=number)

    def test_usual_category_is_available_at_every_counter(self):
        usual_ticket = self.ticket(self.usual)

        self.assertIn(usual_ticket, queueing.waiting_queryset(self.c1))
        self.assertIn(usual_ticket, queueing.waiting_queryset(self.c2))

    def test_exceptional_category_only_at_assigned_counters(self):
        vip_ticket = self.ticket(self.exceptional)

        self.assertIn(vip_ticket, queueing.waiting_queryset(self.c1))
        self.assertNotIn(vip_ticket, queueing.waiting_queryset(self.c2))

    def test_start_call_rejects_a_category_not_assigned_to_the_counter(self):
        vip_ticket = self.ticket(self.exceptional)

        call, reason = queueing.start_call(self.c2, vip_ticket)

        self.assertIsNone(call)
        self.assertEqual(reason, 'not_allowed')
        self.assertFalse(TicketCall.objects.filter(ticket=vip_ticket).exists())


class CallLifecycleTests(QueueTestCase):
    def test_no_show_returns_ticket_to_the_front_of_this_counters_queue(self):
        usual = self.ticket(self.usual, 1)
        later = self.ticket(self.usual, 2)
        call, _ = queueing.start_call(self.c1, usual)

        no_show = queueing.mark_no_show(self.c1, usual)

        usual.refresh_from_db()
        self.assertTrue(no_show.no_show)
        self.assertEqual(usual.status, Ticket.Status.NO_SHOW)
        self.assertEqual(usual.no_show_count, 1)
        self.assertIsNone(usual.current_counter)
        self.assertFalse(call.served)

        waiting = list(queueing.waiting_queryset(self.c1))
        self.assertEqual(waiting[0], usual)
        self.assertEqual(waiting[1], later)

        # A held client can be called again.
        again, reason = queueing.start_call(self.c1, usual)
        usual.refresh_from_db()
        self.assertEqual(reason, 'called')
        self.assertFalse(again.no_show)
        self.assertEqual(usual.status, Ticket.Status.CALLED)
        self.assertEqual(usual.no_show_count, 1)

    def test_done_and_next_records_duration_and_calls_the_next_ticket(self):
        first = self.ticket(self.usual, 1)
        second = self.ticket(self.usual, 2)
        call, _ = queueing.start_call(self.c1, first)
        TicketCall.objects.filter(id=call.id).update(
            called_at=timezone.now() - timedelta(seconds=95)
        )

        finished, called = queueing.done_and_next(self.c1, first)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, Ticket.Status.COMPLETED)
        self.assertIsNotNone(first.completed_at)
        self.assertGreaterEqual(finished.duration_seconds, 95)
        self.assertTrue(finished.served)
        self.assertEqual(second.status, Ticket.Status.CALLED)
        self.assertEqual(second.current_counter, self.c1)
        self.assertEqual(called.ticket_id, second.id)

    def test_calling_a_different_client_finishes_the_previous_one(self):
        first = self.ticket(self.usual, 1)
        second = self.ticket(self.usual, 2)
        first_call, _ = queueing.start_call(self.c1, first)

        queueing.start_call(self.c1, second)

        first_call.refresh_from_db()
        first.refresh_from_db()
        self.assertTrue(first_call.served)
        self.assertIsNotNone(first_call.served_at)
        self.assertEqual(first.status, Ticket.Status.COMPLETED)

    def test_calling_a_ticket_keeps_it_in_the_other_counters_queues(self):
        usual = self.ticket(self.usual)

        queueing.start_call(self.c1, usual)

        self.assertNotIn(usual, queueing.waiting_queryset(self.c1))
        self.assertIn(usual, queueing.waiting_queryset(self.c2))

    def test_a_ticket_can_be_served_at_several_counters(self):
        usual = self.ticket(self.usual)

        first, _ = queueing.start_call(self.c1, usual)
        TicketCall.objects.filter(id=first.id).update(
            called_at=timezone.now() - timedelta(seconds=120)
        )
        queueing.finish_call(self.c1, usual)

        # Done at counter 1 does not finish the client for counter 2.
        self.assertIn(usual, queueing.waiting_queryset(self.c2))

        second, reason = queueing.start_call(self.c2, usual)
        TicketCall.objects.filter(id=second.id).update(
            called_at=timezone.now() - timedelta(seconds=45)
        )
        queueing.finish_call(self.c2, usual)

        self.assertEqual(reason, 'called')
        calls = TicketCall.objects.filter(ticket=usual, served=True).order_by('id')
        self.assertEqual(calls.count(), 2)
        self.assertGreaterEqual(calls[0].duration_seconds, 120)
        self.assertGreaterEqual(calls[1].duration_seconds, 45)

        self.assertNotIn(usual, queueing.waiting_queryset(self.c1))
        self.assertNotIn(usual, queueing.waiting_queryset(self.c2))

    def test_a_second_counter_can_call_a_ticket_already_at_a_station(self):
        usual = self.ticket(self.usual)
        first_call, _ = queueing.start_call(self.c1, usual)

        second_call, reason = queueing.start_call(self.c2, usual)

        first_call.refresh_from_db()
        usual.refresh_from_db()
        self.assertEqual(reason, 'called')
        self.assertFalse(first_call.served)
        self.assertFalse(second_call.served)
        self.assertEqual(usual.status, Ticket.Status.CALLED)
        self.assertEqual(self.c1.id, queueing.active_call(self.c1).counter_id)
        self.assertEqual(self.c2.id, queueing.active_call(self.c2).counter_id)

    def test_no_show_badge_only_shows_on_the_counter_that_missed_the_client(self):
        usual = self.ticket(self.usual)
        queueing.start_call(self.c1, usual)
        queueing.mark_no_show(self.c1, usual)

        first = queueing.build_dashboard_state(self.c1)['waiting'][0]
        second = queueing.build_dashboard_state(self.c2)['waiting'][0]

        self.assertEqual(first['ticket_number'], usual.ticket_number)
        self.assertTrue(first['no_show'])
        self.assertEqual(second['ticket_number'], usual.ticket_number)
        self.assertFalse(second['no_show'])

    def test_recall_does_not_reset_the_station_timer(self):
        usual = self.ticket(self.usual)
        call, _ = queueing.start_call(self.c1, usual)
        original = TicketCall.objects.get(id=call.id).called_at

        recalled = queueing.recall_call(self.c1, usual)
        refreshed = TicketCall.objects.get(id=call.id)

        self.assertTrue(recalled.recalled)
        self.assertEqual(refreshed.recall_count, 1)
        self.assertEqual(refreshed.called_at, original)

    def test_state_groups_waiting_called_and_active(self):
        active = self.ticket(self.usual, 1)
        waiting = self.ticket(self.usual, 2)
        queueing.start_call(self.c1, active)
        queueing.finish_call(self.c1, active)

        queueing.start_call(self.c1, waiting)
        finished_call, _ = queueing.done_and_next(self.c1, waiting)
        self.assertIsNotNone(finished_call)

        state = queueing.build_dashboard_state(self.c1)

        self.assertIn('server_time', state)
        self.assertIsNone(state['active'])
        self.assertEqual(state['called'][0]['ticket_number'], 'A002')
        self.assertGreaterEqual(state['called'][0]['duration_seconds'], 0)


class DashboardApiTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('user1', password='pass')
        CounterUser.objects.create(user=self.user, counter=self.c1)
        self.client.force_login(self.user)

    def test_state_endpoint_returns_the_queue(self):
        usual = self.ticket(self.usual)
        response = self.client.get('/counter/api/state/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['counter']['id'], self.c1.id)
        self.assertEqual(payload['waiting'][0]['ticket_id'], usual.id)
        self.assertIn('dispensed_time', payload['waiting'][0])
        self.assertIsNone(payload['active'])

    def test_counter_feedback_is_saved(self):
        usual = self.ticket(self.usual)
        queueing.start_call(self.c1, usual)

        response = self.client.post(
            '/counter/api/feedback/',
            data=json.dumps({'ticket_id': usual.id, 'rating': 5, 'comment': 'Great'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        feedback = Feedback.objects.get(ticket=usual)
        self.assertEqual(feedback.rating, 5)
        self.assertEqual(feedback.comment, 'Great')
        self.assertEqual(feedback.source, Feedback.Source.COUNTER)
        self.assertEqual(feedback.counter, self.c1)

    def test_counter_feedback_rejects_invalid_rating(self):
        usual = self.ticket(self.usual)
        queueing.start_call(self.c1, usual)

        response = self.client.post(
            '/counter/api/feedback/',
            data=json.dumps({'ticket_id': usual.id, 'rating': 9}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Feedback.objects.filter(ticket=usual).exists())


class PublicFeedbackTests(TestCase):
    def setUp(self):
        self.service = Service.objects.create(name='General', prefix='A', is_usual=True)
        self.ticket = Ticket.objects.create(service=self.service, number=1)

    def test_page_renders_for_a_ticket(self):
        response = self.client.get(f'/feedback/{self.ticket.ticket_number}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket.ticket_number)
        self.assertContains(response, 'How was your visit?')

    def test_public_submission_is_saved(self):
        response = self.client.post(
            f'/feedback/{self.ticket.ticket_number}/',
            {'rating': '4', 'comment': 'Friendly staff'},
        )

        self.assertEqual(response.status_code, 302)
        feedback = Feedback.objects.get(ticket=self.ticket)
        self.assertEqual(feedback.rating, 4)
        self.assertEqual(feedback.comment, 'Friendly staff')
        self.assertEqual(feedback.source, Feedback.Source.PUBLIC)

    def test_invalid_rating_shows_an_error(self):
        response = self.client.post(
            f'/feedback/{self.ticket.ticket_number}/',
            {'rating': '0'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please choose a rating')
        self.assertFalse(Feedback.objects.filter(ticket=self.ticket).exists())


class KioskCategoryTests(TestCase):
    def setUp(self):
        self.general = Service.objects.create(name='General', prefix='A', is_usual=True)
        self.vip = Service.objects.create(name='VIP', prefix='B')

    def test_kiosk_shows_one_button_per_active_category(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-service-id="%s"' % self.general.id)
        self.assertContains(response, 'data-service-id="%s"' % self.vip.id)

    def test_ticket_creation_returns_a_feedback_url(self):
        response = self.client.post(
            '/api/generate/',
            data=json.dumps({'service_id': self.vip.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['ticket_number'], 'B001')
        self.assertTrue(payload['feedback_url'].endswith('/feedback/B001/'))


class DashboardWebSocketTests(TransactionTestCase):
    APP = URLRouter([
        path('ws/dashboard/<int:counter_id>/', DashboardConsumer.as_asgi()),
        path('ws/counter-display/<int:counter_id>/', SingleCounterConsumer.as_asgi()),
        path('ws/display/', DisplayConsumer.as_asgi()),
    ])

    def setUp(self):
        self.service = Service.objects.create(name='General', prefix='A', is_usual=True)
        self.counter = Counter.objects.create(name='Counter 1', display_name='Counter 1')
        self.counter.services.add(self.service)
        self.ticket = Ticket.objects.create(service=self.service, number=1)

    async def test_no_show_is_broadcast_and_display_drops_the_ticket(self):
        display = WebsocketCommunicator(self.APP, '/ws/display/')
        dash = WebsocketCommunicator(self.APP, f'/ws/dashboard/{self.counter.id}/')
        self.assertTrue(await display.connect())
        self.assertTrue(await dash.connect())

        await dash.send_json_to({'action': 'call_ticket', 'ticket_id': self.ticket.id})
        called = await display.receive_json_from(timeout=3)
        self.assertEqual(called['type'], 'ticket_called')

        await dash.send_json_to({'action': 'no_show_ticket', 'ticket_id': self.ticket.id})
        hidden = await display.receive_json_from(timeout=3)
        self.assertEqual(hidden['type'], 'ticket_no_show')
        self.assertEqual(hidden['ticket_number'], 'A001')

        await display.disconnect()
        await dash.disconnect()

    async def test_done_and_next_broadcasts_served_then_called(self):
        next_ticket = await database_sync_to_async(Ticket.objects.create)(
            service=self.service, number=2
        )
        display = WebsocketCommunicator(self.APP, '/ws/display/')
        dash = WebsocketCommunicator(self.APP, f'/ws/dashboard/{self.counter.id}/')
        self.assertTrue(await display.connect())
        self.assertTrue(await dash.connect())

        await dash.send_json_to({'action': 'call_ticket', 'ticket_id': self.ticket.id})
        await display.receive_json_from(timeout=3)

        await dash.send_json_to({'action': 'done_next_ticket', 'ticket_id': self.ticket.id})
        served = await display.receive_json_from(timeout=3)
        called = await display.receive_json_from(timeout=3)

        self.assertEqual(served['type'], 'ticket_served')
        self.assertEqual(served['ticket_number'], 'A001')
        self.assertEqual(called['type'], 'ticket_called')
        self.assertEqual(called['ticket_number'], next_ticket.ticket_number)

        await display.disconnect()
        await dash.disconnect()
