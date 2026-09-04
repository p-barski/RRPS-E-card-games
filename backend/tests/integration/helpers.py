from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from apps.games.models import Player, Room
from apps.games.registry import GAME_REGISTRY
from apps.games.routing import websocket_urlpatterns

application = URLRouter(websocket_urlpatterns)


def connect_player(room_code: str, player_id: str) -> WebsocketCommunicator:
    return WebsocketCommunicator(
        application,
        f"/ws/rooms/{room_code}/",
        headers=[(b"cookie", f"player_id={player_id}".encode())],
    )


async def receive_of_type(communicator: WebsocketCommunicator, message_type: str) -> dict:
    """Pops messages until one of `message_type` arrives, discarding any
    interleaved "presence" frames (connect/disconnect elsewhere in the room
    can push one into a queue at a nondeterministic point relative to the
    message a test actually cares about)."""
    while True:
        message = await communicator.receive_json_from()
        if message.get("type") == message_type:
            return message


async def receive_state(communicator: WebsocketCommunicator) -> dict:
    return await receive_of_type(communicator, "state")


async def receive_error(communicator: WebsocketCommunicator) -> dict:
    return await receive_of_type(communicator, "error")


@database_sync_to_async
def create_room_with_players(game_type: str, seat0_player_id: str, seat1_player_id: str | None, bot_seat1: bool = False):
    spec = GAME_REGISTRY[game_type]
    room = Room.objects.create(
        game_type=game_type,
        state=spec.initial_state().to_dict(),
        status=Room.Status.ACTIVE,
    )
    Player.objects.create(room=room, player_id=seat0_player_id, seat=0)
    if bot_seat1:
        Player.objects.create(room=room, player_id="bot", seat=1, is_bot=True, display_name="Bot")
    elif seat1_player_id:
        Player.objects.create(room=room, player_id=seat1_player_id, seat=1)
    return room.code


@database_sync_to_async
def get_room_state(room_code: str) -> dict:
    return Room.objects.get(code=room_code).state
