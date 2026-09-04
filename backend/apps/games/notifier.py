"""GameNotifier is the DI seam for "how does a state update reach clients".

ChannelsGameNotifier is what production wiring (GameConsumer) uses. Tests
that only want to check engine/consumer orchestration without touching the
channel layer can inject a fake with the same `broadcast` signature.
"""

from typing import Protocol

from apps.games.groups import seat_group_name


class GameNotifier(Protocol):
    async def broadcast(self, room_code: str, payload_by_seat: dict[int, dict]) -> None: ...


class ChannelsGameNotifier:
    def __init__(self, channel_layer):
        self.channel_layer = channel_layer

    async def broadcast(self, room_code: str, payload_by_seat: dict[int, dict]) -> None:
        for seat, payload in payload_by_seat.items():
            await self.channel_layer.group_send(
                seat_group_name(room_code, seat),
                {"type": "game.state", "payload": payload},
            )
