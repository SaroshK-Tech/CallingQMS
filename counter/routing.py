from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dashboard/(?P<counter_id>\d+)/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'ws/counter-display/(?P<counter_id>\d+)/$', consumers.SingleCounterConsumer.as_asgi()),
]
