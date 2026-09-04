import pytest
from django.test import override_settings

from tests.integration.helpers import connect_player, create_room_with_players, receive_state

pytestmark = pytest.mark.django_db(transaction=True)


def alice_move(state):
    """Plays citizen while she still has one this match, otherwise her
    side's special card — always a legal choice whenever it's her turn."""
    if state["hand"]["0"].get("citizen", 0) > 0:
        return "citizen"
    return state["side_of"]["0"]


def current_turn_seat(state):
    first = state["match_first_picker"] if state["round_number"] % 2 == 1 else 1 - state["match_first_picker"]
    return first if state["pending"][str(first)] is None else 1 - first


@override_settings(BOT_MOVE_DELAY_MIN_SECONDS=0, BOT_MOVE_DELAY_MAX_SECONDS=0, MIN_SECONDS_BETWEEN_MOVES=0)
async def test_human_vs_bot_full_12_match_game():
    room_code = await create_room_with_players("ecard", "alice", None, bot_seat1=True)
    alice = connect_player(room_code, "alice")
    connected, _ = await alice.connect()
    assert connected
    state = (await receive_state(alice))["state"]

    # The bot now waits its turn like a real player instead of reactively
    # tagging along on alice's message, so only submit when it's genuinely
    # her turn and otherwise just drain the bot's own broadcast.
    for _ in range(300):
        if state["status"] == "finished":
            break
        if current_turn_seat(state) == 0:
            await alice.send_json_to({"type": "submit_move", "card": alice_move(state)})
        reply = await receive_state(alice)
        assert reply["type"] == "state", reply
        state = reply["state"]

    assert state["status"] == "finished"
    assert len(state["matches_history"]) == 12
    total = state["total_points"]["0"] + state["total_points"]["1"]
    awarded = sum(m["points_awarded"] for m in state["matches_history"])
    assert total == awarded
    if state["total_points"]["0"] == state["total_points"]["1"]:
        assert state["winner_seat"] is None
    else:
        expected = 0 if state["total_points"]["0"] > state["total_points"]["1"] else 1
        assert state["winner_seat"] == expected

    await alice.disconnect()


@override_settings(MIN_SECONDS_BETWEEN_MOVES=0)
async def test_human_vs_human_side_switch_and_redaction():
    room_code = await create_room_with_players("ecard", "alice", "bob")
    alice = connect_player(room_code, "alice")
    bob = connect_player(room_code, "bob")
    await alice.connect()
    await bob.connect()
    alice_init = (await receive_state(alice))["state"]
    bob_init = (await receive_state(bob))["state"]
    # Which seat starts as Emperor is randomized (see apps.ecard.engine's
    # emperor_start_seat) — this test only cares that the two seats hold
    # opposite sides, not which one specifically.
    alice_side = alice_init["side_of"]["0"]
    bob_side = bob_init["side_of"]["1"]
    assert {alice_side, bob_side} == {"emperor", "slave"}

    # Round 1 (seat 0 picks first in odd-numbered matches, regardless of
    # side): draw.
    await alice.send_json_to({"type": "submit_move", "card": "citizen"})
    alice_partial = (await receive_state(alice))["state"]
    bob_partial = (await receive_state(bob))["state"]
    assert alice_partial["pending"]["0"] == "citizen"
    assert bob_partial["pending"]["0"] == "hidden"

    await bob.send_json_to({"type": "submit_move", "card": "citizen"})
    await receive_state(alice)
    round1_result = (await receive_state(bob))["state"]
    assert round1_result["round_number"] == 2

    # Round 2 (first-picker flips to bob): draw.
    await bob.send_json_to({"type": "submit_move", "card": "citizen"})
    await receive_state(alice)
    await receive_state(bob)
    await alice.send_json_to({"type": "submit_move", "card": "citizen"})
    await receive_state(alice)
    round2_result = (await receive_state(bob))["state"]
    assert round2_result["round_number"] == 3

    # Round 3 (first-picker back to alice): whoever holds Emperor-side
    # plays their special card, the other plays citizen -> Emperor side
    # wins match 1 for 1 point, match 2 begins with sides unchanged.
    alice_card = "emperor" if alice_side == "emperor" else "citizen"
    bob_card = "emperor" if bob_side == "emperor" else "citizen"
    await alice.send_json_to({"type": "submit_move", "card": alice_card})
    await receive_state(alice)
    await receive_state(bob)
    await bob.send_json_to({"type": "submit_move", "card": bob_card})
    alice_final = (await receive_state(alice))["state"]
    bob_final = (await receive_state(bob))["state"]

    expected_winner_seat = 0 if alice_side == "emperor" else 1
    expected_points = {"0": 0, "1": 0}
    expected_points[str(expected_winner_seat)] = 1

    assert alice_final["total_points"] == expected_points
    assert alice_final["match_number"] == 2
    assert alice_final["side_of"] == alice_init["side_of"]  # unchanged within the first 3-match block
    assert bob_final["total_points"] == expected_points

    await alice.disconnect()
    await bob.disconnect()
