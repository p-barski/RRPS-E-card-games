from rest_framework import status as http_status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.games.models import Player, Room
from apps.games.registry import GAME_REGISTRY

BOT_PLAYER_ID = "bot"
BOT_DISPLAY_NAME = "Bot"
MAX_DISPLAY_NAME_LENGTH = 40


@api_view(["POST"])
def create_room(request):
    game_type = request.data.get("game_type")
    if game_type not in GAME_REGISTRY:
        return Response({"detail": "Unknown game_type."}, status=http_status.HTTP_400_BAD_REQUEST)

    vs_bot = bool(request.data.get("vs_bot"))
    display_name = str(request.data.get("display_name") or "").strip()[:MAX_DISPLAY_NAME_LENGTH]

    spec = GAME_REGISTRY[game_type]
    room = Room.objects.create(
        game_type=game_type,
        state=spec.initial_state().to_dict(),
        status=Room.Status.ACTIVE if vs_bot else Room.Status.WAITING,
    )
    Player.objects.create(room=room, player_id=request.player_id, seat=0, display_name=display_name)
    if vs_bot:
        Player.objects.create(
            room=room, player_id=BOT_PLAYER_ID, seat=1, is_bot=True, display_name=BOT_DISPLAY_NAME
        )

    return Response(_room_payload(room, seat=0), status=http_status.HTTP_201_CREATED)


@api_view(["POST"])
def join_room(request, code):
    try:
        room = Room.objects.get(code=code)
    except Room.DoesNotExist:
        return Response({"detail": "Room not found."}, status=http_status.HTTP_404_NOT_FOUND)

    existing = room.players.filter(player_id=request.player_id).first()
    if existing is not None:
        return Response(_room_payload(room, seat=existing.seat))

    if room.status != Room.Status.WAITING or room.players.count() >= 2:
        return Response({"detail": "Room is not joinable."}, status=http_status.HTTP_400_BAD_REQUEST)

    display_name = str(request.data.get("display_name") or "").strip()[:MAX_DISPLAY_NAME_LENGTH]
    player = Player.objects.create(room=room, player_id=request.player_id, seat=1, display_name=display_name)
    room.status = Room.Status.ACTIVE
    room.save(update_fields=["status"])

    return Response(_room_payload(room, seat=player.seat))


@api_view(["GET"])
def get_room(request, code):
    try:
        room = Room.objects.get(code=code)
    except Room.DoesNotExist:
        return Response({"detail": "Room not found."}, status=http_status.HTTP_404_NOT_FOUND)

    player = room.players.filter(player_id=request.player_id).first()
    if player is None:
        return Response({"detail": "Not a participant in this room."}, status=http_status.HTTP_404_NOT_FOUND)

    return Response(_room_payload(room, seat=player.seat))


def _room_payload(room: Room, seat: int) -> dict:
    return {
        "code": room.code,
        "game_type": room.game_type,
        "status": room.status,
        "seat": seat,
        "player_count": room.players.count(),
    }
