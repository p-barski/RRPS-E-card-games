"""Pure game logic for Restricted Rock-Paper-Scissors.

No Django/network/global-random imports here on purpose: this module is the
DI seam the plan calls for. RPSEngine and RandomRPSBot take a random.Random
via their constructor so tests can inject a seeded one for determinism, while
production wiring injects a real random.Random().
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from apps.games.exceptions import IllegalMoveError

CARDS = ("rock", "paper", "scissors")
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
STARTING_STARS = 3
CARDS_PER_TYPE = 4
MAX_ROUNDS = len(CARDS) * CARDS_PER_TYPE


@dataclass
class RPSState:
    stars: dict[str, int]
    hand: dict[str, dict[str, int]]
    pending: dict[str, str | None]
    rounds_played: int = 0
    history: list[dict] = field(default_factory=list)
    status: str = "in_progress"  # "in_progress" | "finished"
    winner_seat: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "RPSState":
        return RPSState(**data)


def initial_state() -> RPSState:
    hand = {card: CARDS_PER_TYPE for card in CARDS}
    return RPSState(
        stars={"0": STARTING_STARS, "1": STARTING_STARS},
        hand={"0": dict(hand), "1": dict(hand)},
        pending={"0": None, "1": None},
    )


class RPSEngine:
    def next_movers(self, state: RPSState) -> list[int]:
        """Seats allowed to submit a move right now (order doesn't matter
        in RPS — both can move independently as long as they haven't
        already played this round)."""
        if state.status != "in_progress":
            return []
        return [seat for seat in (0, 1) if state.pending[str(seat)] is None]

    def apply_move(self, state: RPSState, seat: int, card: str) -> RPSState:
        if state.status != "in_progress":
            raise IllegalMoveError("Game is already finished.")
        if card not in CARDS:
            raise IllegalMoveError(f"Unknown card: {card!r}")

        seat_key = str(seat)
        other_key = "1" if seat_key == "0" else "0"

        if state.pending[seat_key] is not None:
            raise IllegalMoveError("You already played a card this round.")
        if state.hand[seat_key][card] <= 0:
            raise IllegalMoveError(f"No {card} cards left.")

        pending = dict(state.pending)
        hand = {seat: dict(cards) for seat, cards in state.hand.items()}
        pending[seat_key] = card
        hand[seat_key][card] -= 1

        stars = dict(state.stars)
        history = list(state.history)
        rounds_played = state.rounds_played
        status = state.status
        winner_seat = state.winner_seat

        if pending[other_key] is not None:
            seat0_card, seat1_card = pending["0"], pending["1"]
            round_winner = self._resolve_round(seat0_card, seat1_card)
            if round_winner is not None:
                loser = 1 - round_winner
                stars[str(round_winner)] += 1
                stars[str(loser)] -= 1
            history.append(
                {"seat0_card": seat0_card, "seat1_card": seat1_card, "winner_seat": round_winner}
            )
            rounds_played += 1
            pending = {"0": None, "1": None}

            if stars["0"] == 0 or stars["1"] == 0:
                status = "finished"
                winner_seat = 0 if stars["1"] == 0 else 1
            elif rounds_played >= MAX_ROUNDS:
                status = "finished"
                winner_seat = None if stars["0"] == stars["1"] else (
                    0 if stars["0"] > stars["1"] else 1
                )

        return RPSState(
            stars=stars,
            hand=hand,
            pending=pending,
            rounds_played=rounds_played,
            history=history,
            status=status,
            winner_seat=winner_seat,
        )

    @staticmethod
    def _resolve_round(card0: str, card1: str) -> int | None:
        if card0 == card1:
            return None
        return 0 if BEATS[card0] == card1 else 1


class RandomRPSBot:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    def choose_move(self, state: RPSState, seat: int) -> str:
        hand = state.hand[str(seat)]
        available = [card for card in CARDS if hand[card] > 0]
        return self.rng.choice(available)
