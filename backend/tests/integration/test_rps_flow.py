import pytest
from django.test import override_settings

from tests.integration.helpers import connect_player, create_room_with_players, receive_error, receive_state

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(MIN_SECONDS_BETWEEN_MOVES=0)
async def test_human_vs_human_full_game_and_redaction():
    room_code = await create_room_with_players("rps", "alice", "bob")

    alice = connect_player(room_code, "alice")
    bob = connect_player(room_code, "bob")
    connected, _ = await alice.connect()
    assert connected
    connected, _ = await bob.connect()
    assert connected

    await receive_state(alice)  # initial state
    await receive_state(bob)

    # Round 1: alice plays first. Bob's connection shouldn't see alice's
    # card in the clear before he's moved too.
    await alice.send_json_to({"type": "submit_move", "card": "rock"})
    alice_partial = (await receive_state(alice))["state"]
    bob_partial = (await receive_state(bob))["state"]
    assert alice_partial["pending"]["0"] == "rock"
    assert alice_partial["pending"]["1"] is None
    assert bob_partial["pending"]["0"] == "hidden"

    await bob.send_json_to({"type": "submit_move", "card": "scissors"})
    alice_state = (await receive_state(alice))["state"]
    bob_state = (await receive_state(bob))["state"]
    assert alice_state["stars"] == {"0": 4, "1": 2}
    assert bob_state["stars"] == {"0": 4, "1": 2}
    assert alice_state["pending"] == {"0": None, "1": None}

    # alice keeps winning with rock vs scissors until bob is eliminated.
    for _ in range(2):
        await alice.send_json_to({"type": "submit_move", "card": "rock"})
        await receive_state(alice)
        await receive_state(bob)
        await bob.send_json_to({"type": "submit_move", "card": "scissors"})
        alice_state = (await receive_state(alice))["state"]
        bob_state = (await receive_state(bob))["state"]

    assert alice_state["status"] == "finished"
    assert alice_state["winner_seat"] == 0
    assert alice_state["stars"] == {"0": 6, "1": 0}
    assert bob_state == alice_state | {"your_seat": 1}

    await alice.disconnect()
    await bob.disconnect()


@override_settings(BOT_MOVE_DELAY_MIN_SECONDS=0, BOT_MOVE_DELAY_MAX_SECONDS=0, MIN_SECONDS_BETWEEN_MOVES=0)
async def test_human_vs_bot_full_game():
    room_code = await create_room_with_players("rps", "alice", None, bot_seat1=True)

    alice = connect_player(room_code, "alice")
    connected, _ = await alice.connect()
    assert connected
    state = (await receive_state(alice))["state"]  # initial state

    def alice_move(state):
        hand = state["hand"]["0"]
        return next(card for card in ("rock", "paper", "scissors") if hand.get(card, 0) > 0)

    # The bot now plays independently ~0-1.5s after a round starts rather
    # than strictly reacting to alice, so her move and the bot's can land
    # in either order across separate broadcasts — only submit when she
    # hasn't already played this round, and always drain the next message.
    for _ in range(40):
        if state["status"] == "finished":
            break
        if state["pending"]["0"] is None:
            await alice.send_json_to({"type": "submit_move", "card": alice_move(state)})
        state = (await receive_state(alice))["state"]

    assert state["status"] == "finished"
    assert state["winner_seat"] is None or state["winner_seat"] in (0, 1)
    assert state["stars"]["0"] + state["stars"]["1"] == 6
    await alice.disconnect()


@override_settings(MIN_SECONDS_BETWEEN_MOVES=1000)
async def test_rate_limit_rejects_rapid_resubmission():
    room_code = await create_room_with_players("rps", "alice", "bob")
    alice = connect_player(room_code, "alice")
    bob = connect_player(room_code, "bob")
    await alice.connect()
    await bob.connect()
    await receive_state(alice)
    await receive_state(bob)

    await alice.send_json_to({"type": "submit_move", "card": "rock"})
    await receive_state(alice)
    await receive_state(bob)

    await alice.send_json_to({"type": "submit_move", "card": "paper"})
    error = await receive_error(alice)
    assert error["type"] == "error"

    await alice.disconnect()
    await bob.disconnect()


async def test_illegal_move_returns_error_not_a_crash():
    room_code = await create_room_with_players("rps", "alice", "bob")
    alice = connect_player(room_code, "alice")
    await alice.connect()
    await receive_state(alice)

    await alice.send_json_to({"type": "submit_move", "card": "lizard"})
    error = await receive_error(alice)
    assert error["type"] == "error"

    await alice.disconnect()
