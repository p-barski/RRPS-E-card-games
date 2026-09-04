from http.cookies import SimpleCookie

from django.conf import settings


def player_id_from_asgi_scope(scope) -> str | None:
    """Reads the anonymous player id cookie out of a Channels ASGI scope.

    Channels' ASGI scope carries raw headers, not Django's parsed request,
    so the cookie has to be parsed by hand here.
    """
    headers = dict(scope.get("headers") or [])
    raw_cookie = headers.get(b"cookie")
    if not raw_cookie:
        return None
    cookie = SimpleCookie()
    cookie.load(raw_cookie.decode("latin-1"))
    morsel = cookie.get(settings.PLAYER_ID_COOKIE_NAME)
    return morsel.value if morsel else None
