import asyncio
import random
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from apps.games.exceptions import IllegalMoveError
from apps.games.groups import seat_group_name
from apps.games.models import Player, Room
from apps.games.notifier import ChannelsGameNotifier
from apps.games.redaction import redact_for_seat
from apps.games.registry import GAME_REGISTRY
from apps.players.cookies import player_id_from_asgi_scope


class GameConsumer(AsyncJsonWebsocketConsumer):
    notifier_class = ChannelsGameNotifier  # DI seam: swappable in tests

    async def connect(self):
        self.room_code = self.scope["url_route"]["kwargs"]["code"]
        self.player_id = player_id_from_asgi_scope(self.scope)
        self._last_move_at: float | None = None
        self._bot_move_scheduled = False
        self._bot_task: asyncio.Task | None = None
        # Guards the read-apply-save-broadcast sequence: the bot's delayed
        # move and this connection's own receive_json both mutate the same
        # room row, and without this a lost-update race is easy to hit
        # (both read the pre-move state, then the second save clobbers the
        # first instead of building on it).
        self._state_lock = asyncio.Lock()

        if not self.player_id:
            await self.close(code=4001)
            return

        loaded = await self._load_room_and_seat()
        if loaded is None:
            await self.close(code=4004)
            return
        room, seat = loaded
        self.seat = seat
        self.notifier = self.notifier_class(self.channel_layer)
        self.group_name = seat_group_name(self.room_code, self.seat)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._set_connected(True)
        connected = await self._connected_seats()
        names = await self._seat_names()
        await self.send_json(
            {
                "type": "state",
                "state": redact_for_seat(room.state, self.seat),
                "connected": connected,
                "names": names,
            }
        )
        await self._notify_other_of_presence(connected)
        await self._maybe_schedule_bot_move()

    async def disconnect(self, code):
        if self._bot_task is not None:
            self._bot_task.cancel()
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "seat"):
            # A room only ever stays WAITING while its creator is the sole
            # player (joining flips it to ACTIVE in the same request that
            # creates seat 1) — so if it's still WAITING here, this
            # connection was that creator and no one else can ever reach
            # this room's other seat. Deleting it now avoids leaving a
            # permanently-empty row for the sweep command to find later.
            deleted = await self._delete_if_abandoned()
            if not deleted:
                await self._set_connected(False)
                connected = await self._connected_seats()
                await self._notify_other_of_presence(connected)

    async def _notify_other_of_presence(self, connected: dict[str, bool]) -> None:
        other_seat = 1 - self.seat
        names = await self._seat_names()
        await self.channel_layer.group_send(
            seat_group_name(self.room_code, other_seat),
            {"type": "game.presence", "payload": {"type": "presence", "connected": connected, "names": names}},
        )

    async def receive_json(self, content, **kwargs):
        if content.get("type") != "submit_move":
            return

        now = time.monotonic()
        if self._last_move_at is not None and now - self._last_move_at < settings.MIN_SECONDS_BETWEEN_MOVES:
            await self.send_json({"type": "error", "message": "You're moving too fast."})
            return
        self._last_move_at = now

        async with self._state_lock:
            room = await self._get_room()
            spec = GAME_REGISTRY[room.game_type]
            engine = spec.engine_class()
            state = spec.state_class.from_dict(room.state)

            try:
                state = engine.apply_move(state, self.seat, content.get("card"))
            except IllegalMoveError as exc:
                await self.send_json({"type": "error", "message": str(exc)})
                return

            await self._save_state(room, state)
            await self._broadcast(state)
        await self._maybe_schedule_bot_move()

    async def _maybe_schedule_bot_move(self):
        """If a bot needs to move right now, schedule it to actually play
        after a random think delay — timed from when the round/turn
        started, not from when the human plays, so the bot's pace is the
        same every round instead of stacking on top of however long the
        human took (and, for games where both seats can move independently,
        instead of the bot racing ahead into a round the human hasn't
        reached yet)."""
        if self._bot_move_scheduled:
            return

        room = await self._get_room()
        spec = GAME_REGISTRY[room.game_type]
        engine = spec.engine_class()
        state = spec.state_class.from_dict(room.state)
        bot_seats = await self._bot_seats(room)
        bot_mover = next((s for s in engine.next_movers(state) if s in bot_seats), None)
        if bot_mover is None:
            return

        self._bot_move_scheduled = True
        delay = random.uniform(settings.BOT_MOVE_DELAY_MIN_SECONDS, settings.BOT_MOVE_DELAY_MAX_SECONDS)
        self._bot_task = asyncio.create_task(self._delayed_bot_move(bot_mover, delay))

    async def _delayed_bot_move(self, seat, delay):
        await asyncio.sleep(delay)

        async with self._state_lock:
            room = await self._get_room()
            spec = GAME_REGISTRY[room.game_type]
            engine = spec.engine_class()
            state = spec.state_class.from_dict(room.state)
            bot_seats = await self._bot_seats(room)

            if seat in bot_seats and seat in engine.next_movers(state):
                move = spec.bot_class().choose_move(state, seat)
                try:
                    state = engine.apply_move(state, seat, move)
                except IllegalMoveError:
                    state = None
                if state is not None:
                    await self._save_state(room, state)
                    await self._broadcast(state)

        self._bot_move_scheduled = False
        await self._maybe_schedule_bot_move()

    async def _broadcast(self, state):
        state_dict = state.to_dict()
        payload_by_seat = {
            seat: {"type": "state", "state": redact_for_seat(state_dict, seat)} for seat in (0, 1)
        }
        await self.notifier.broadcast(self.room_code, payload_by_seat)

    @database_sync_to_async
    def _load_room_and_seat(self):
        try:
            room = Room.objects.get(code=self.room_code)
            player = room.players.get(player_id=self.player_id)
        except (Room.DoesNotExist, Player.DoesNotExist):
            return None
        return room, player.seat

    @database_sync_to_async
    def _get_room(self):
        return Room.objects.get(code=self.room_code)

    @database_sync_to_async
    def _bot_seats(self, room):
        return set(room.players.filter(is_bot=True).values_list("seat", flat=True))

    @database_sync_to_async
    def _delete_if_abandoned(self) -> bool:
        deleted, _ = Room.objects.filter(code=self.room_code, status=Room.Status.WAITING).delete()
        return deleted > 0

    @database_sync_to_async
    def _set_connected(self, value: bool) -> None:
        Player.objects.filter(room__code=self.room_code, seat=self.seat).update(is_connected=value)

    @database_sync_to_async
    def _connected_seats(self) -> dict[str, bool]:
        players = Player.objects.filter(room__code=self.room_code).values("seat", "is_bot", "is_connected")
        return {str(p["seat"]): (p["is_bot"] or p["is_connected"]) for p in players}

    @database_sync_to_async
    def _seat_names(self) -> dict[str, str]:
        players = Player.objects.filter(room__code=self.room_code).values("seat", "display_name")
        return {str(p["seat"]): (p["display_name"].strip() or "Anonymous player") for p in players}

    @database_sync_to_async
    def _save_state(self, room, state):
        room.state = state.to_dict()
        if state.status == "finished":
            room.status = Room.Status.FINISHED
        room.save(update_fields=["state", "status"])

    async def game_state(self, event):
        await self.send_json(event["payload"])

    async def game_presence(self, event):
        await self.send_json(event["payload"])
