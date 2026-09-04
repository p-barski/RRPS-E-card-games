from django.urls import re_path

from apps.games.consumer import GameConsumer

websocket_urlpatterns = [
    re_path(r"^ws/rooms/(?P<code>\w+)/$", GameConsumer.as_asgi()),
]
