import random

import pytest

from apps.ecard.engine import (
    ECardEngine,
    ECardState,
    RandomECardBot,
    _first_picker_for_match,
    _initial_hand,
    _side_for_match,
    initial_state,
)
from apps.games.exceptions import IllegalMoveError


def play_round(engine, state, seat_cards):
    """Submits both seats' cards for one round, in whichever order the
    engine's turn enforcement actually accepts (round-level first-picker
    alternates, so callers shouldn't need to track it themselves).
    """
    seats = list(seat_cards)
    try:
        state = engine.apply_move(state, seats[0], seat_cards[seats[0]])
        state = engine.apply_move(state, seats[1], seat_cards[seats[1]])
    except IllegalMoveError:
        state = engine.apply_move(state, seats[1], seat_cards[seats[1]])
        state = engine.apply_move(state, seats[0], seat_cards[seats[0]])
    return state


def cards_for_match(state, emperor_card, slave_card):
    emperor_seat = 0 if state.side_of["0"] == "emperor" else 1
    slave_seat = 1 - emperor_seat
    return {emperor_seat: emperor_card, slave_seat: slave_card}


def emperor0_initial_state() -> ECardState:
    """A start state equivalent to what initial_state() builds whenever the
    randomized coin flip lands on seat 0 — used by tests that are about a
    resolution rule, not about the randomization itself, so they don't need
    to care which seat starts as Emperor."""
    side_of = _side_for_match(1, 0)
    return ECardState(
        total_points={"0": 0, "1": 0},
        match_number=1,
        side_of=side_of,
        match_first_picker=_first_picker_for_match(1),
        round_number=1,
        pending={"0": None, "1": None},
        hand=_initial_hand(side_of),
        emperor_start_seat=0,
    )


def test_initial_state_shape():
    state = emperor0_initial_state()
    assert state.side_of == {"0": "emperor", "1": "slave"}
    assert state.match_first_picker == 0
    assert state.hand["0"] == {"citizen": 4, "emperor": 1}
    assert state.hand["1"] == {"citizen": 4, "slave": 1}
    assert state.match_number == 1
    assert state.round_number == 1
    assert state.total_points == {"0": 0, "1": 0}


def test_initial_state_emperor_start_seat_is_randomized():
    # Not always the same seat across games (this used to always be seat 0).
    results = {initial_state(random.Random(seed)).emperor_start_seat for seed in range(20)}
    assert results == {0, 1}


def test_initial_state_side_of_matches_the_randomized_emperor_start_seat():
    for seed in range(6):
        state = initial_state(random.Random(seed))
        assert state.side_of == _side_for_match(1, state.emperor_start_seat)


def test_citizen_vs_citizen_is_a_draw_and_continues():
    engine = ECardEngine()
    state = play_round(engine, initial_state(), cards_for_match(initial_state(), "citizen", "citizen"))
    assert state.round_number == 2
    assert state.match_number == 1
    assert state.pending == {"0": None, "1": None}
    assert state.match_rounds[-1]["winner_seat"] is None


def test_emperor_beats_citizen_emperor_side_wins_1_point():
    engine = ECardEngine()
    state = emperor0_initial_state()
    state = play_round(engine, state, cards_for_match(state, "emperor", "citizen"))
    assert state.total_points == {"0": 1, "1": 0}
    assert state.match_number == 2
    assert state.matches_history[-1]["winner_seat"] == 0
    assert state.matches_history[-1]["points_awarded"] == 1


def test_slave_loses_to_citizen_emperor_side_still_wins():
    engine = ECardEngine()
    state = emperor0_initial_state()
    state = play_round(engine, state, cards_for_match(state, "citizen", "slave"))
    assert state.total_points == {"0": 1, "1": 0}
    assert state.matches_history[-1]["winner_seat"] == 0


def test_slave_beats_emperor_slave_side_wins_5_points():
    engine = ECardEngine()
    state = emperor0_initial_state()
    state = play_round(engine, state, cards_for_match(state, "emperor", "slave"))
    assert state.total_points == {"0": 0, "1": 5}
    assert state.matches_history[-1]["winner_seat"] == 1
    assert state.matches_history[-1]["points_awarded"] == 5


def test_fourth_round_draw_auto_resolves_slave_win_without_a_manual_move():
    engine = ECardEngine()
    state = emperor0_initial_state()
    for _ in range(4):
        state = play_round(engine, state, cards_for_match(state, "citizen", "citizen"))

    assert state.match_number == 2
    assert state.total_points == {"0": 0, "1": 5}
    last_match = state.matches_history[-1]
    assert last_match["winner_seat"] == 1
    assert len(last_match["rounds"]) == 5
    assert last_match["rounds"][-1]["auto_resolved"] is True


def test_round_first_picker_alternates_within_a_match():
    engine = ECardEngine()
    state = initial_state()

    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 1, "citizen")  # seat 1 can't go first in round 1
    state = engine.apply_move(state, 0, "citizen")
    state = engine.apply_move(state, 1, "citizen")
    assert state.round_number == 2

    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 0, "citizen")  # first-picker flips to seat 1 in round 2
    state = engine.apply_move(state, 1, "citizen")
    state = engine.apply_move(state, 0, "citizen")
    assert state.round_number == 3


def test_match_first_picker_alternates_by_match_number():
    assert _first_picker_for_match(1) == 0
    assert _first_picker_for_match(2) == 1
    assert _first_picker_for_match(3) == 0
    assert _first_picker_for_match(12) == 1


def test_side_switch_schedule_matches_the_stated_example():
    seat0_emperor_matches = {n for n in range(1, 13) if _side_for_match(n, 0)["0"] == "emperor"}
    assert seat0_emperor_matches == {1, 2, 3, 7, 8, 9}


def test_side_switch_schedule_is_relative_to_whichever_seat_started_as_emperor():
    # Same cadence, just mirrored when seat 1 won the initial coin flip.
    seat0_emperor_matches = {n for n in range(1, 13) if _side_for_match(n, 1)["0"] == "emperor"}
    assert seat0_emperor_matches == {4, 5, 6, 10, 11, 12}


def test_cannot_play_the_opposing_sides_special_card():
    engine = ECardEngine()
    state = emperor0_initial_state()
    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 0, "slave")  # seat 0 is emperor side this match
    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 1, "emperor")


def test_cannot_play_out_of_turn_after_already_moving():
    engine = ECardEngine()
    state = engine.apply_move(initial_state(), 0, "citizen")
    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 0, "citizen")


def test_full_game_tied_points_is_a_draw():
    engine = ECardEngine()
    state = initial_state()
    # Slave always wins (5 pts); over 12 matches each seat holds the slave
    # side exactly 6 times, so this nets an exact 30-30 tie.
    for _ in range(12):
        state = play_round(engine, state, cards_for_match(state, "emperor", "slave"))

    assert state.status == "finished"
    assert state.total_points == {"0": 30, "1": 30}
    assert state.winner_seat is None
    assert len(state.matches_history) == 12


def test_full_game_winner_by_total_points():
    engine = ECardEngine()
    state = initial_state()
    # Seat 0 wins every match regardless of which side it holds that match.
    for _ in range(12):
        if state.side_of["0"] == "emperor":
            cards = cards_for_match(state, "emperor", "citizen")  # emperor side (seat 0) wins, 1 pt
        else:
            cards = cards_for_match(state, "emperor", "slave")  # slave side (seat 0) wins, 5 pts
        state = play_round(engine, state, cards)

    assert state.status == "finished"
    assert state.match_number == 12
    assert state.total_points == {"0": 36, "1": 0}
    assert state.winner_seat == 0


def test_next_movers_is_exactly_the_seat_whose_turn_it_is():
    engine = ECardEngine()
    state = initial_state()
    assert engine.next_movers(state) == [0]
    state = engine.apply_move(state, 0, "citizen")
    assert engine.next_movers(state) == [1]


def test_next_movers_empty_once_finished():
    engine = ECardEngine()
    state = initial_state()
    for _ in range(12):
        state = play_round(engine, state, cards_for_match(state, "emperor", "slave"))
    assert state.status == "finished"
    assert engine.next_movers(state) == []


def test_bot_only_chooses_available_cards():
    engine = ECardEngine()
    bot = RandomECardBot(rng=random.Random(1))
    state = engine.apply_move(emperor0_initial_state(), 0, "emperor")  # seat 0 hand now citizen:4 only
    for _ in range(50):
        assert bot.choose_move(state, 0) == "citizen"


def test_bot_is_deterministic_given_same_seed():
    state = initial_state()
    moves_a = [RandomECardBot(rng=random.Random(7)).choose_move(state, 1) for _ in range(10)]
    moves_b = [RandomECardBot(rng=random.Random(7)).choose_move(state, 1) for _ in range(10)]
    assert moves_a == moves_b
