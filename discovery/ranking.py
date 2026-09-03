import re

from discovery.filters import (
    company_size_score,
)

from discovery.salary import (
    salary_score,
)

def calculate_discovery_score(
    distance_km: float | None,
    company_size: str,
    published_salary_min: float | None,
    published_salary_max: float | None,
    estimated_salary_min: float | None,
    estimated_salary_max: float | None,
    initial_fit_score: float,
    maximum_radius_km: float = 50.0,
    minimum_salary: float = 80000,
) -> float:

    geo_score = location_score(
        distance_km,
        maximum_radius_km,
    )

    company_score = (
        company_size_score(
            company_size
        )
    )

    pay_score = salary_score(
        published_salary_min,
        published_salary_max,
        estimated_salary_min,
        estimated_salary_max,
        minimum_salary,
    )


    discovery_score = (
        geo_score * 0.25
        + company_score * 0.20
        + pay_score * 0.30
        + initial_fit_score * 0.25
    )


    return round(
        discovery_score,
        1,
    )


def normalize_text(
    value: str,
) -> str:

    if not value:
        return ""

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9+#.\- ]",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()

def initial_candidate_fit_score(
    candidate_data: dict,
    job_title: str,
    job_description: str,
) -> float:

    if not candidate_data:
        return 0.0

    candidate_parts = []

    for key in [
        "professional_summary",
        "skills",
        "technical_skills",
        "experience",
    ]:

        value = candidate_data.get(
            key
        )

        if isinstance(
            value,
            list,
        ):

            candidate_parts.extend(
                str(item)
                for item in value
            )

        elif value:

            candidate_parts.append(
                str(value)
            )


    candidate_text = normalize_text(
        " ".join(
            candidate_parts
        )
    )


    job_text = normalize_text(
        f"{job_title} {job_description}"
    )


    if not candidate_text:
        return 0.0

    candidate_words = set(
        candidate_text.split()
    )

    job_words = set(
        job_text.split()
    )


    if not candidate_words:
        return 0.0


    overlap = (
        candidate_words
        & job_words
    )


    score = (
        len(overlap)
        / len(candidate_words)
    ) * 100


    return min(
        score,
        100.0,
    )

def location_score(
    distance_km: float | None,
    maximum_radius_km: float = 50.0,
) -> float:

    if distance_km is None:
        return 0.0

    if distance_km > maximum_radius_km:
        return 0.0

    score = (
        1
        - (
            distance_km
            / maximum_radius_km
        )
    ) * 100

    return max(
        0.0,
        score,
    )