def redact_for_seat(state_dict: dict, seat: int) -> dict:
    """Hides the opponent's face-down pending card.

    Both RPS and E-card states expose a `pending: {"0": ..., "1": ...}`
    dict, so one redaction function covers both games: everything else
    (hands, stars/points, history) is information either player could
    already derive from revealed rounds, so it's sent as-is.
    """
    other_key = "1" if str(seat) == "0" else "0"
    pending = dict(state_dict["pending"])
    if pending.get(other_key) is not None:
        pending[other_key] = "hidden"
    return {**state_dict, "pending": pending, "your_seat": seat}
