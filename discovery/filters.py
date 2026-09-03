ALLOWED_COMPANY_SIZES = {
    "Medium",
    "Large",
}


def company_size_allowed(
    company_size: str,
) -> bool:

    if not company_size:
        return True

    normalized = (
        company_size
        .strip()
        .title()
    )

    if normalized == "Unknown":
        return True

    return (
        normalized
        in ALLOWED_COMPANY_SIZES
    )


def company_size_score(
    company_size: str,
) -> float:

    if not company_size:
        return 50.0

    normalized = (
        company_size
        .strip()
        .title()
    )

    scores = {
        "Large": 100.0,
        "Medium": 85.0,
        "Small": 30.0,
        "Unknown": 50.0,
    }

    return scores.get(
        normalized,
        50.0,
    )