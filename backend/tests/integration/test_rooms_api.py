import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # AnonRateThrottle keys its history on ident+scope, which the Django
    # test client's fixed REMOTE_ADDR makes shared across tests in this
    # module unless we reset it — otherwise these tests order-depend on
    # each other's request counts.
    cache.clear()


def test_create_room_vs_bot_is_active_immediately():
    client = APIClient()
    resp = client.post("/api/rooms/", {"game_type": "rps", "vs_bot": True}, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["seat"] == 0
    assert body["player_count"] == 2
    assert "player_id" in resp.cookies


def test_create_room_waits_for_opponent_and_join_activates_it():
    creator = APIClient()
    create_resp = creator.post("/api/rooms/", {"game_type": "ecard"}, format="json")
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["status"] == "waiting"
    assert body["player_count"] == 1
    code = body["code"]

    joiner = APIClient()
    join_resp = joiner.post(f"/api/rooms/{code}/join/", {"display_name": "bob"}, format="json")
    assert join_resp.status_code == 200
    join_body = join_resp.json()
    assert join_body["status"] == "active"
    assert join_body["seat"] == 1

    get_resp = creator.get(f"/api/rooms/{code}/")
    assert get_resp.json()["status"] == "active"


def test_join_unknown_room_returns_404():
    client = APIClient()
    resp = client.post("/api/rooms/ZZZZZZ/join/", {}, format="json")
    assert resp.status_code == 404


def test_third_player_cannot_join_a_full_room():
    creator = APIClient()
    code = creator.post("/api/rooms/", {"game_type": "rps"}, format="json").json()["code"]
    second = APIClient()
    second.post(f"/api/rooms/{code}/join/", {}, format="json")

    third = APIClient()
    resp = third.post(f"/api/rooms/{code}/join/", {}, format="json")
    assert resp.status_code == 400


def test_unknown_game_type_rejected():
    client = APIClient()
    resp = client.post("/api/rooms/", {"game_type": "chess"}, format="json")
    assert resp.status_code == 400


def test_non_participant_cannot_fetch_room():
    creator = APIClient()
    code = creator.post("/api/rooms/", {"game_type": "rps"}, format="json").json()["code"]
    stranger = APIClient()
    resp = stranger.get(f"/api/rooms/{code}/")
    assert resp.status_code == 404


def test_room_create_is_rate_limited(monkeypatch):
    # AnonRateThrottle.THROTTLE_RATES is snapshotted from settings at import
    # time, so overriding settings.REST_FRAMEWORK at test-time doesn't
    # reliably reach it — patch the class attribute the throttle actually
    # reads instead.
    from rest_framework.throttling import AnonRateThrottle

    monkeypatch.setattr(AnonRateThrottle, "THROTTLE_RATES", {"anon": "2/min"})
    client = APIClient()
    for _ in range(2):
        resp = client.post("/api/rooms/", {"game_type": "rps", "vs_bot": True}, format="json")
        assert resp.status_code == 201
    resp = client.post("/api/rooms/", {"game_type": "rps", "vs_bot": True}, format="json")
    assert resp.status_code == 429
