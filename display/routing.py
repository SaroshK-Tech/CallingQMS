from django.urls import re_path
from counter.consumers import DisplayConsumer

websocket_urlpatterns = [
    re_path(r'ws/display/$', DisplayConsumer.as_asgi()),
]
