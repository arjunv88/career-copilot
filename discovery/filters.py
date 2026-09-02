def location_is_allowed(
    distance_km: float | None,
    radius_km: float = 50.0,
):

    if distance_km is None:
        return False

    return (
        distance_km <= radius_km
    )