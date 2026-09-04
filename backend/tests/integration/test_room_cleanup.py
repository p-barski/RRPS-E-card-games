from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from django.core.management import call_command
from django.utils import timezone

from apps.games.models import Player, Room
from apps.games.registry import GAME_REGISTRY
from tests.integration.helpers import connect_player, create_room_with_players, receive_state

pytestmark = pytest.mark.django_db(transaction=True)


@database_sync_to_async
def create_waiting_room(game_type: str, player_id: str) -> str:
    """A room with only its creator seated, mirroring what POST /api/rooms/
    produces for a non-bot game before anyone joins — status stays WAITING
    until a second player is added (see views.join_room)."""
    spec = GAME_REGISTRY[game_type]
    room = Room.objects.create(
        game_type=game_type, state=spec.initial_state().to_dict(), status=Room.Status.WAITING
    )
    Player.objects.create(room=room, player_id=player_id, seat=0)
    return room.code


async def test_creator_disconnect_before_anyone_joins_deletes_the_room():
    room_code = await create_waiting_room("rps", "alice")
    alice = connect_player(room_code, "alice")
    connected, _ = await alice.connect()
    assert connected
    await receive_state(alice)

    await alice.disconnect()

    exists = await Room.objects.filter(code=room_code).aexists()
    assert exists is False


async def test_disconnect_after_opponent_joined_does_not_delete_the_room():
    room_code = await create_room_with_players("rps", "alice", "bob")
    alice = connect_player(room_code, "alice")
    bob = connect_player(room_code, "bob")
    await alice.connect()
    await bob.connect()
    await receive_state(alice)
    await receive_state(bob)

    await alice.disconnect()
    # bob still sees a presence update rather than the connection just
    # vanishing, which is only possible if the room row is still there.
    presence = await bob.receive_json_from()
    assert presence["type"] == "presence"

    exists = await Room.objects.filter(code=room_code).aexists()
    assert exists is True

    await bob.disconnect()


async def test_disconnect_from_bot_game_does_not_delete_the_room():
    room_code = await create_room_with_players("rps", "alice", None, bot_seat1=True)
    alice = connect_player(room_code, "alice")
    await alice.connect()
    await receive_state(alice)

    await alice.disconnect()

    exists = await Room.objects.filter(code=room_code).aexists()
    assert exists is True


def _make_room(game_type: str, status: str, age: timedelta) -> Room:
    room = Room.objects.create(game_type=game_type, status=status)
    Room.objects.filter(id=room.id).update(created_at=timezone.now() - age)
    return room


def test_cleanup_command_deletes_old_waiting_rooms_but_keeps_recent_ones(db):
    old_waiting = _make_room("rps", Room.Status.WAITING, timedelta(minutes=90))
    recent_waiting = _make_room("rps", Room.Status.WAITING, timedelta(minutes=5))

    call_command("cleanup_stale_rooms")

    assert not Room.objects.filter(id=old_waiting.id).exists()
    assert Room.objects.filter(id=recent_waiting.id).exists()


def test_cleanup_command_deletes_any_room_past_the_hard_age_limit(db):
    ancient_active = _make_room("ecard", Room.Status.ACTIVE, timedelta(hours=48))
    ancient_finished = _make_room("rps", Room.Status.FINISHED, timedelta(hours=25))
    recent_active = _make_room("rps", Room.Status.ACTIVE, timedelta(hours=1))

    call_command("cleanup_stale_rooms")

    assert not Room.objects.filter(id=ancient_active.id).exists()
    assert not Room.objects.filter(id=ancient_finished.id).exists()
    assert Room.objects.filter(id=recent_active.id).exists()


def test_cleanup_command_dry_run_deletes_nothing(db, capsys):
    old_waiting = _make_room("rps", Room.Status.WAITING, timedelta(minutes=90))

    call_command("cleanup_stale_rooms", "--dry-run")

    assert Room.objects.filter(id=old_waiting.id).exists()
    out = capsys.readouterr().out
    assert "Would delete 1 stale room" in out
