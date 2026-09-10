"""
ASGI config for EQMS-AlgoriSync project.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eqms.settings')

django_asgi_app = get_asgi_application()

from counter.routing import websocket_urlpatterns as counter_ws
from display.routing import websocket_urlpatterns as display_ws

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(counter_ws + display_ws)
    ),
})
