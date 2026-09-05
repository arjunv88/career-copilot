"""
Career Copilot - Week 5 discovery ranking.

This module performs a deliberately lightweight first-pass ranking of
discovered vacancies.  It is NOT the final compatibility engine; the C++
matcher remains responsible for detailed compatibility after a job has
been parsed.

The goal here is to answer:
    "Is this vacancy promising enough to investigate further?"
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

from discovery.filters import company_size_score
from discovery.salary import salary_score


# Words that are too generic to be useful when comparing role titles.
_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "engineer",
    "engineering",
    "entwickler",
    "entwicklerin",
    "developer",
    "entwicklung",
    "for",
    "für",
    "in",
    "m",
    "mit",
    "of",
    "or",
    "senior",
    "software",
    "the",
    "und",
    "w",
    "d",
}

# Candidate fields that contain explicit, useful technical signals.
_CANDIDATE_TERM_FIELDS = (
    "technical_skills",
    "programming_languages",
    "tools",
    "methodologies",
    "industries",
)

# A small amount of normalization for terminology that commonly appears
# in several textual forms.  This is intentionally conservative: discovery
# ranking should not invent skills the candidate does not have.
_TERM_ALIASES = {
    "c++": ("c++", "cpp"),
    "c#": ("c#", "c sharp"),
    ".net": (".net", "dotnet"),
    "ci/cd": ("ci/cd", "ci cd", "continuous integration", "continuous delivery"),
    "matlab/simulink": ("matlab simulink", "matlab", "simulink"),
    "iso 26262": ("iso 26262", "iso26262"),
    "autosar": ("autosar", "classic autosar", "adaptive autosar"),
}


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value to a finite float without allowing NaN/inf through."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _clamp(
    value: Any,
    lower: float = 0.0,
    upper: float = 100.0,
) -> float:
    """Return a finite value clamped to the requested range."""

    number = _safe_float(value, lower)
    return min(max(number, lower), upper)


def normalize_text(
    value: Any,
) -> str:
    """
    Normalize free text while preserving useful technical characters.

    Examples preserved reasonably well:
      C++, C#, .NET, AUTOSAR, ISO-26262
    """

    if value is None:
        return ""

    text = str(value).lower()

    # Normalize common separators before removing punctuation.
    text = text.replace("_", " ")
    text = text.replace("/", " ")

    # Keep characters that matter for common technical names.
    text = re.sub(
        r"[^a-z0-9+#.\- ]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _normalize_term(
    value: Any,
) -> str:
    """Normalize a skill/technology phrase for matching."""

    return normalize_text(value).strip(" .-")


def _iter_string_values(
    value: Any,
) -> Iterable[str]:
    """
    Yield string values from lists/tuples/sets or scalar values.

    Dictionaries are deliberately not flattened generically because that
    can add irrelevant keys/representation text into the ranking signal.
    """

    if value is None:
        return

    if isinstance(
        value,
        (list, tuple, set),
    ):
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    yield cleaned
        return

    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            yield cleaned


def _candidate_terms(
    candidate_data: dict,
) -> list[str]:
    """
    Extract explicit candidate skills/technologies from the approved profile.

    Also uses the technologies listed in employment history, because the
    CandidateProfile schema stores valuable technical evidence there.
    """

    terms: list[str] = []

    for field_name in _CANDIDATE_TERM_FIELDS:
        terms.extend(
            _iter_string_values(
                candidate_data.get(field_name)
            )
        )

    employment_history = candidate_data.get(
        "employment_history",
        [],
    )

    if isinstance(
        employment_history,
        list,
    ):
        for entry in employment_history:
            if not isinstance(entry, dict):
                continue

            terms.extend(
                _iter_string_values(
                    entry.get("technologies")
                )
            )

    # Stable de-duplication after normalization.
    unique_terms: list[str] = []
    seen: set[str] = set()

    for term in terms:
        normalized = _normalize_term(term)

        # Single-character generic terms are too noisy.  C and R are valid
        # languages but produce unacceptable substring false positives in
        # arbitrary prose, so the discovery pre-screen intentionally avoids
        # treating them as phrase matches.
        if len(normalized) < 2:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        unique_terms.append(normalized)

    return unique_terms


def _term_variants(
    term: str,
) -> tuple[str, ...]:
    """Return conservative textual variants for one candidate term."""

    normalized = _normalize_term(term)

    if normalized in _TERM_ALIASES:
        return tuple(
            _normalize_term(item)
            for item in _TERM_ALIASES[normalized]
            if _normalize_term(item)
        )

    # Hyphenated technical names often appear with spaces.
    variants = {
        normalized,
        normalized.replace("-", " "),
    }

    return tuple(
        value
        for value in variants
        if value
    )


def _contains_term(
    normalized_job_text: str,
    term: str,
) -> bool:
    """
    Phrase-match a candidate term against normalized job text.

    Word-boundary handling avoids obvious substring problems such as
    matching 'can' inside 'candidate'.
    """

    if not normalized_job_text or not term:
        return False

    for variant in _term_variants(term):
        escaped = re.escape(variant)

        pattern = (
            rf"(?<![a-z0-9+#])"
            rf"{escaped}"
            rf"(?![a-z0-9+#])"
        )

        if re.search(
            pattern,
            normalized_job_text,
        ):
            return True

    return False


def _title_tokens(
    value: Any,
) -> set[str]:
    """Return informative title tokens only."""

    normalized = normalize_text(value)

    tokens = {
        token.strip(".-")
        for token in normalized.split()
    }

    return {
        token
        for token in tokens
        if (
            len(token) >= 2
            and token not in _TITLE_STOPWORDS
        )
    }


def _title_similarity_score(
    candidate_title: str,
    job_title: str,
) -> float:
    """
    Lightweight Jaccard-style similarity between role titles.

    This is only a small component of initial fit, so it cannot overpower
    explicit skill evidence.
    """

    candidate_tokens = _title_tokens(
        candidate_title
    )
    job_tokens = _title_tokens(
        job_title
    )

    if not candidate_tokens or not job_tokens:
        return 0.0

    overlap = (
        candidate_tokens
        & job_tokens
    )

    if not overlap:
        return 0.0

    union = (
        candidate_tokens
        | job_tokens
    )

    return _clamp(
        (
            len(overlap)
            / max(len(union), 1)
        )
        * 100.0
    )


def _skill_match_score(
    matched_count: int,
) -> float:
    """
    Convert the number of explicit candidate-skill matches into a useful
    discovery score.

    A saturating scale is preferable to dividing by every skill on a long
    CV.  The previous implementation did exactly that and produced values
    such as ~3.8% even for plausible embedded roles.
    """

    if matched_count <= 0:
        return 0.0

    score_by_count = {
        1: 25.0,
        2: 40.0,
        3: 55.0,
        4: 68.0,
        5: 78.0,
        6: 86.0,
        7: 93.0,
    }

    return score_by_count.get(
        matched_count,
        100.0,
    )


def initial_candidate_fit_score(
    candidate_data: dict,
    job_title: str,
    job_description: str,
) -> float:
    """
    Calculate a lightweight initial fit score from 0 to 100.

    Components:
      - 85% explicit candidate skill/technology matches
      - 15% informative role-title similarity

    This is deliberately permissive and should NOT be interpreted as final
    compatibility.  Detailed matching belongs to the existing C++ engine.
    """

    if not isinstance(
        candidate_data,
        dict,
    ) or not candidate_data:
        return 0.0

    job_title = str(
        job_title or ""
    )
    job_description = str(
        job_description or ""
    )

    normalized_job_text = normalize_text(
        f"{job_title} {job_description}"
    )

    if not normalized_job_text:
        return 0.0

    terms = _candidate_terms(
        candidate_data
    )

    matched_terms = [
        term
        for term in terms
        if _contains_term(
            normalized_job_text,
            term,
        )
    ]

    skill_score = _skill_match_score(
        len(matched_terms)
    )

    title_score = _title_similarity_score(
        str(
            candidate_data.get(
                "professional_title",
                "",
            )
        ),
        job_title,
    )

    score = (
        skill_score * 0.85
        + title_score * 0.15
    )

    return round(
        _clamp(score),
        1,
    )


def location_score(
    distance_km: float | None,
    maximum_radius_km: float = 50.0,
) -> float:
    """
    Score proximity within the allowed radius.

    0 km -> 100
    radius boundary -> 0
    outside radius / unknown -> 0
    """

    radius = _safe_float(
        maximum_radius_km,
        0.0,
    )

    if radius <= 0.0:
        return 0.0

    if distance_km is None:
        return 0.0

    distance = _safe_float(
        distance_km,
        -1.0,
    )

    if distance < 0.0:
        return 0.0

    if distance > radius:
        return 0.0

    score = (
        1.0
        - (
            distance
            / radius
        )
    ) * 100.0

    return round(
        _clamp(score),
        1,
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
    """
    Calculate the overall Week-5 discovery score.

    Weights intentionally remain aligned with the W5 design:
      location       25%
      company size   20%
      salary         30%
      initial fit    25%
    """

    geo_score = location_score(
        distance_km,
        maximum_radius_km,
    )

    company_score = _clamp(
        company_size_score(
            company_size
        )
    )

    pay_score = _clamp(
        salary_score(
            published_salary_min,
            published_salary_max,
            estimated_salary_min,
            estimated_salary_max,
            minimum_salary,
        )
    )

    fit_score = _clamp(
        initial_fit_score
    )

    discovery_score = (
        geo_score * 0.25
        + company_score * 0.20
        + pay_score * 0.30
        + fit_score * 0.25
    )

    return round(
        _clamp(discovery_score),
        1,
    )
