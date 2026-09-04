"""Pure game logic for E-card.

Same DI pattern as apps.rps.engine: ECardEngine is stateless and
RandomECardBot takes a random.Random via its constructor so tests can inject
a seeded one.

Rules encoded here (see the plan for the full derivation):
- 12 matches. Each match: one seat is Emperor-side (citizen x4 + emperor x1),
  the other Slave-side (citizen x4 + slave x1). Hands are fresh every match.
- Seat 0 is Emperor-side for matches where ((match_number-1)//3) is even
  (matches 1-3, 7-9), Slave-side otherwise (4-6, 10-12).
- Each round: citizen-vs-citizen draws (continue); any other combination
  resolves the match immediately. Since each side only ever holds citizen
  plus its own special card, "any other combination" is exactly emperor-vs-
  citizen or citizen-vs-slave (both Emperor-side wins) or emperor-vs-slave
  (Slave-side wins).
- If round 4 is also a draw, the engine auto-resolves emperor-vs-slave
  (Slave-side wins) with no further player input.
- Points: Emperor-side match win = 1 point, Slave-side match win = 5 points,
  credited to whichever player held that side in that match.
- Round-level first-picker alternates every round within a match. Match-level
  first-picker alternates every match by seat: seat 0 first in odd matches,
  seat 1 first in even matches.
- Overall winner: highest total points after match 12; equal = draw.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from apps.games.exceptions import IllegalMoveError

TOTAL_MATCHES = 12
MATCHES_PER_SIDE_BLOCK = 3
CITIZENS_PER_MATCH = 4
ROUNDS_PER_MATCH = CITIZENS_PER_MATCH


@dataclass
class ECardState:
    total_points: dict[str, int]
    match_number: int
    side_of: dict[str, str]          # seat -> "emperor" | "slave", for the current match
    match_first_picker: int          # seat that picks first in round 1 of this match
    round_number: int                # 1..4 within the current match
    pending: dict[str, str | None]   # this round's face-down picks
    hand: dict[str, dict[str, int]]  # this match's remaining cards per seat
    emperor_start_seat: int = 0      # seat that was Emperor-side in match 1 (randomized at game start)
    match_rounds: list[dict] = field(default_factory=list)
    matches_history: list[dict] = field(default_factory=list)
    status: str = "in_progress"      # "in_progress" | "finished"
    winner_seat: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "ECardState":
        return ECardState(**data)


def _first_picker_for_match(match_number: int) -> int:
    return 0 if match_number % 2 == 1 else 1


def _side_for_match(match_number: int, emperor_start_seat: int) -> dict[str, str]:
    same_block_as_start = ((match_number - 1) // MATCHES_PER_SIDE_BLOCK) % 2 == 0
    emperor_seat = emperor_start_seat if same_block_as_start else 1 - emperor_start_seat
    return {"0": "emperor", "1": "slave"} if emperor_seat == 0 else {"0": "slave", "1": "emperor"}


def _initial_hand(side_of: dict[str, str]) -> dict[str, dict[str, int]]:
    return {seat: {"citizen": CITIZENS_PER_MATCH, side: 1} for seat, side in side_of.items()}


def initial_state(rng: random.Random | None = None) -> ECardState:
    rng = rng or random.Random()
    emperor_start_seat = rng.choice((0, 1))
    side_of = _side_for_match(1, emperor_start_seat)
    return ECardState(
        total_points={"0": 0, "1": 0},
        match_number=1,
        side_of=side_of,
        match_first_picker=_first_picker_for_match(1),
        round_number=1,
        pending={"0": None, "1": None},
        hand=_initial_hand(side_of),
        emperor_start_seat=emperor_start_seat,
    )


class ECardEngine:
    def next_movers(self, state: ECardState) -> list[int]:
        """The single seat allowed to move right now (E-card enforces a
        strict pick order), or [] once the game is finished."""
        if state.status != "in_progress":
            return []
        return [self._current_turn_seat(state)]

    def apply_move(self, state: ECardState, seat: int, card: str) -> ECardState:
        if state.status != "in_progress":
            raise IllegalMoveError("Game is already finished.")

        seat_key = str(seat)
        other_key = "1" if seat_key == "0" else "0"

        expected_seat = self._current_turn_seat(state)
        if seat != expected_seat:
            raise IllegalMoveError("Not your turn.")

        side = state.side_of[seat_key]
        if card not in ("citizen", side):
            raise IllegalMoveError(f"{card!r} is not a valid card for the {side} side.")
        if state.hand[seat_key].get(card, 0) <= 0:
            raise IllegalMoveError(f"No {card} cards left.")

        pending = dict(state.pending)
        hand = {s: dict(cards) for s, cards in state.hand.items()}
        pending[seat_key] = card
        hand[seat_key][card] -= 1

        total_points = dict(state.total_points)
        match_rounds = list(state.match_rounds)
        matches_history = list(state.matches_history)
        match_number = state.match_number
        side_of = dict(state.side_of)
        match_first_picker = state.match_first_picker
        round_number = state.round_number
        status = state.status
        winner_seat = state.winner_seat

        if pending[other_key] is not None:
            emperor_key = "0" if side_of["0"] == "emperor" else "1"
            slave_key = "1" if emperor_key == "0" else "0"
            emperor_card, slave_card = pending[emperor_key], pending[slave_key]

            winner_side = self._resolve_match_round(emperor_card, slave_card)
            match_rounds.append(
                {
                    "round_number": round_number,
                    "seat0_card": pending["0"],
                    "seat1_card": pending["1"],
                    "winner_seat": self._winner_seat_for_side(winner_side, emperor_key, slave_key),
                }
            )

            if winner_side is None and round_number == ROUNDS_PER_MATCH:
                winner_side = "slave"
                match_rounds.append(
                    {
                        "round_number": round_number + 1,
                        "seat0_card": side_of["0"],
                        "seat1_card": side_of["1"],
                        "winner_seat": int(slave_key),
                        "auto_resolved": True,
                    }
                )

            if winner_side is not None:
                match_winner_seat = self._winner_seat_for_side(winner_side, emperor_key, slave_key)
                points = 1 if winner_side == "emperor" else 5
                total_points[str(match_winner_seat)] += points
                matches_history.append(
                    {
                        "match_number": match_number,
                        "emperor_seat": int(emperor_key),
                        "winner_seat": match_winner_seat,
                        "points_awarded": points,
                        "rounds": match_rounds,
                    }
                )

                if match_number >= TOTAL_MATCHES:
                    status = "finished"
                    p0, p1 = total_points["0"], total_points["1"]
                    winner_seat = None if p0 == p1 else (0 if p0 > p1 else 1)
                    round_number = 0
                    pending = {"0": None, "1": None}
                    match_rounds = []
                else:
                    match_number += 1
                    side_of = _side_for_match(match_number, state.emperor_start_seat)
                    match_first_picker = _first_picker_for_match(match_number)
                    round_number = 1
                    pending = {"0": None, "1": None}
                    hand = _initial_hand(side_of)
                    match_rounds = []
            else:
                round_number += 1
                pending = {"0": None, "1": None}

        return ECardState(
            total_points=total_points,
            match_number=match_number,
            side_of=side_of,
            match_first_picker=match_first_picker,
            round_number=round_number,
            pending=pending,
            hand=hand,
            emperor_start_seat=state.emperor_start_seat,
            match_rounds=match_rounds,
            matches_history=matches_history,
            status=status,
            winner_seat=winner_seat,
        )

    @staticmethod
    def _resolve_match_round(emperor_card: str, slave_card: str) -> str | None:
        if emperor_card == "citizen" and slave_card == "citizen":
            return None
        if emperor_card == "emperor" and slave_card == "slave":
            return "slave"
        return "emperor"

    @staticmethod
    def _winner_seat_for_side(winner_side: str | None, emperor_key: str, slave_key: str) -> int | None:
        if winner_side is None:
            return None
        return int(emperor_key) if winner_side == "emperor" else int(slave_key)

    @staticmethod
    def _round_first_picker(state: ECardState) -> int:
        other = 1 - state.match_first_picker
        return state.match_first_picker if state.round_number % 2 == 1 else other

    def _current_turn_seat(self, state: ECardState) -> int:
        first = self._round_first_picker(state)
        return first if state.pending[str(first)] is None else 1 - first


class RandomECardBot:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    def choose_move(self, state: ECardState, seat: int) -> str:
        hand = state.hand[str(seat)]
        available = [card for card, count in hand.items() if count > 0]
        return self.rng.choice(available)
