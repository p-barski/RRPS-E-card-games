import uuid

from django.conf import settings


class AnonymousPlayerMiddleware:
    """Gives every browser a stable anonymous identity via an HttpOnly cookie.

    Not a Django session — just a bare uuid used to identify seats in a Room.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        player_id = request.COOKIES.get(settings.PLAYER_ID_COOKIE_NAME)
        is_new = player_id is None
        if is_new:
            player_id = str(uuid.uuid4())
        request.player_id = player_id

        response = self.get_response(request)

        if is_new:
            response.set_cookie(
                settings.PLAYER_ID_COOKIE_NAME,
                player_id,
                max_age=settings.PLAYER_ID_COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax" if settings.DEBUG else "None",
                secure=not settings.DEBUG,
            )
        return response
