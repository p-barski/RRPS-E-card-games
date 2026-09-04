import uuid

from django.db import models


def generate_room_code() -> str:
    return uuid.uuid4().hex[:6].upper()


class Room(models.Model):
    class GameType(models.TextChoices):
        RPS = "rps", "Restricted Rock Paper Scissors"
        ECARD = "ecard", "E-card"

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting for opponent"
        ACTIVE = "active", "In progress"
        FINISHED = "finished", "Finished"

    code = models.CharField(max_length=8, unique=True, default=generate_room_code)
    game_type = models.CharField(max_length=8, choices=GameType.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.WAITING)
    state = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.code} ({self.game_type})"


class Player(models.Model):
    room = models.ForeignKey(Room, related_name="players", on_delete=models.CASCADE)
    player_id = models.CharField(max_length=64)
    seat = models.PositiveSmallIntegerField()
    is_bot = models.BooleanField(default=False)
    display_name = models.CharField(max_length=40, blank=True)
    is_connected = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["room", "seat"], name="unique_seat_per_room"),
        ]

    def __str__(self) -> str:
        return f"{self.display_name or self.player_id} (seat {self.seat})"
