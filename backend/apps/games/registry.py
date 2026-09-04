from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apps.ecard.engine import ECardEngine, ECardState, RandomECardBot
from apps.ecard.engine import initial_state as ecard_initial_state
from apps.rps.engine import RandomRPSBot, RPSEngine, RPSState
from apps.rps.engine import initial_state as rps_initial_state


@dataclass(frozen=True)
class GameSpec:
    engine_class: type
    bot_class: type
    state_class: type
    initial_state: Callable[[], Any]


GAME_REGISTRY: dict[str, GameSpec] = {
    "rps": GameSpec(RPSEngine, RandomRPSBot, RPSState, rps_initial_state),
    "ecard": GameSpec(ECardEngine, RandomECardBot, ECardState, ecard_initial_state),
}
