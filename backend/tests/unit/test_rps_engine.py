import random

import pytest

from apps.rps.engine import IllegalMoveError, RandomRPSBot, RPSEngine, RPSState, initial_state


def play_round(engine, state, card0, card1):
    state = engine.apply_move(state, 0, card0)
    state = engine.apply_move(state, 1, card1)
    return state


def test_initial_state():
    state = initial_state()
    assert state.stars == {"0": 3, "1": 3}
    assert state.hand["0"] == {"rock": 4, "paper": 4, "scissors": 4}
    assert state.hand["1"] == {"rock": 4, "paper": 4, "scissors": 4}
    assert state.pending == {"0": None, "1": None}
    assert state.status == "in_progress"


def test_draw_round_no_star_change():
    engine = RPSEngine()
    state = play_round(engine, initial_state(), "rock", "rock")
    assert state.stars == {"0": 3, "1": 3}
    assert state.pending == {"0": None, "1": None}
    assert state.hand["0"]["rock"] == 3
    assert state.hand["1"]["rock"] == 3
    assert state.rounds_played == 1
    assert state.history[-1] == {"seat0_card": "rock", "seat1_card": "rock", "winner_seat": None}


def test_win_transfers_a_star_not_just_decrements():
    engine = RPSEngine()
    state = play_round(engine, initial_state(), "rock", "scissors")
    assert state.stars == {"0": 4, "1": 2}
    assert state.history[-1]["winner_seat"] == 0

    state = play_round(engine, state, "scissors", "rock")
    assert state.stars == {"0": 3, "1": 3}


def test_pending_is_hidden_until_both_play():
    engine = RPSEngine()
    state = initial_state()
    state = engine.apply_move(state, 0, "paper")
    assert state.pending == {"0": "paper", "1": None}
    assert state.rounds_played == 0


def test_cannot_play_twice_before_opponent():
    engine = RPSEngine()
    state = engine.apply_move(initial_state(), 0, "rock")
    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 0, "paper")


def test_cannot_play_exhausted_card():
    engine = RPSEngine()
    state = initial_state()
    for _ in range(4):
        state = play_round(engine, state, "rock", "rock")
    assert state.hand["0"]["rock"] == 0
    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 0, "rock")


def test_cannot_play_unknown_card():
    engine = RPSEngine()
    with pytest.raises(IllegalMoveError):
        engine.apply_move(initial_state(), 0, "lizard")


def test_game_ends_on_elimination_before_12_rounds():
    engine = RPSEngine()
    state = initial_state()
    # seat 0 wins three straight rounds: 3 -> 4 -> 5 -> 6, seat 1: 3 -> 2 -> 1 -> 0
    for _ in range(3):
        state = play_round(engine, state, "rock", "scissors")
    assert state.status == "finished"
    assert state.winner_seat == 0
    assert state.stars == {"0": 6, "1": 0}
    assert state.rounds_played == 3

    with pytest.raises(IllegalMoveError):
        engine.apply_move(state, 0, "paper")


def _state_at_final_round(stars, hand0_card, hand1_card):
    """Builds the state right before round 12, holding exactly one card
    each so the final round's outcome is unambiguous. RPSState is a plain
    dataclass, so constructing an intermediate state directly (rather than
    hand-tracing 11 prior rounds) keeps this test focused on the
    exhaustion/tie-break branch it's actually checking.
    """
    empty = {"rock": 0, "paper": 0, "scissors": 0}
    return RPSState(
        stars=dict(stars),
        hand={"0": {**empty, hand0_card: 1}, "1": {**empty, hand1_card: 1}},
        pending={"0": None, "1": None},
        rounds_played=11,
        history=[],
        status="in_progress",
        winner_seat=None,
    )


def test_game_ends_after_12_rounds_with_unequal_stars():
    engine = RPSEngine()
    state = _state_at_final_round({"0": 4, "1": 2}, "rock", "scissors")
    state = play_round(engine, state, "rock", "scissors")

    assert state.rounds_played == 12
    assert state.status == "finished"
    assert state.stars == {"0": 5, "1": 1}
    assert state.winner_seat == 0


def test_game_ends_in_draw_at_3_3_after_12_rounds():
    engine = RPSEngine()
    state = _state_at_final_round({"0": 4, "1": 2}, "scissors", "rock")
    state = play_round(engine, state, "scissors", "rock")

    assert state.rounds_played == 12
    assert state.status == "finished"
    assert state.stars == {"0": 3, "1": 3}
    assert state.winner_seat is None


def test_next_movers_excludes_seats_that_already_played():
    engine = RPSEngine()
    state = initial_state()
    assert set(engine.next_movers(state)) == {0, 1}
    state = engine.apply_move(state, 0, "rock")
    assert engine.next_movers(state) == [1]


def test_next_movers_empty_once_finished():
    engine = RPSEngine()
    state = initial_state()
    for _ in range(3):
        state = play_round(engine, state, "rock", "scissors")
    assert state.status == "finished"
    assert engine.next_movers(state) == []


def test_bot_only_chooses_available_cards():
    engine = RPSEngine()
    bot = RandomRPSBot(rng=random.Random(1))
    state = initial_state()
    for _ in range(4):
        state = play_round(engine, state, "rock", "rock")
    assert state.hand["1"]["rock"] == 0
    for _ in range(50):
        move = bot.choose_move(state, 1)
        assert move in ("paper", "scissors")


def test_bot_is_deterministic_given_same_seed():
    state = initial_state()
    moves_a = [RandomRPSBot(rng=random.Random(42)).choose_move(state, 0) for _ in range(10)]
    moves_b = [RandomRPSBot(rng=random.Random(42)).choose_move(state, 0) for _ in range(10)]
    assert moves_a == moves_b
