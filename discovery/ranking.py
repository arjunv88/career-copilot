"""Career Copilot discovery ranking.

Discovery ranking is deliberately separate from the downstream C++ compatibility
engine.  It answers: "Is this vacancy worth analysing in detail?"
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

from discovery.filters import company_size_score
from discovery.salary import salary_score


TITLE_STOPWORDS = {
    "a", "an", "and", "at", "der", "die", "das", "ein", "eine", "for", "für",
    "in", "m", "mit", "of", "or", "the", "und", "w", "d", "f", "mwd",
}

# Conservative families: variants inside a family are treated as the same
# discovery signal, not as proof of full job compatibility.
TERM_FAMILIES: dict[str, tuple[str, ...]] = {
    "cpp": ("c++", "cpp", "modern c++", "c++17", "c++20"),
    "embedded": ("embedded software", "embedded systems", "firmware", "embedded c", "embedded c++"),
    "autosar": ("autosar", "classic autosar", "adaptive autosar"),
    "functional_safety": ("iso 26262", "iso26262", "functional safety", "asil", "asil-d", "asil d"),
    "matlab_simulink": ("matlab", "simulink", "matlab simulink"),
    "hil": ("hil", "hardware in the loop", "hardware-in-the-loop"),
    "sil": ("sil", "software in the loop", "software-in-the-loop"),
    "dil": ("dil", "driver in the loop", "driver-in-the-loop"),
    "ci_cd": ("ci/cd", "ci cd", "continuous integration", "continuous delivery", "jenkins"),
    "requirements": ("requirements engineering", "requirements management", "doors", "ibm doors"),
    "architecture": ("system architecture", "software architecture", "technical architecture", "uml", "mbse", "mbsd"),
    "validation": ("verification validation", "verification & validation", "validation", "system validation", "testing"),
    "simulation": ("simulation", "real-time simulation", "virtual validation", "rapid prototyping", "carmaker", "dspace"),
    "controls": ("control engineering", "control systems", "controls", "controller development"),
    "can": ("can", "canoe", "canape"),
    "ethernet": ("ethernet", "automotive ethernet"),
    "python": ("python",),
    "cmake": ("cmake", "build systems"),
    "git": ("git",),
}

DOMAIN_FAMILIES: dict[str, tuple[str, ...]] = {
    "automotive": ("automotive", "vehicle", "ecu", "steering", "adas"),
    "embedded": ("embedded", "firmware", "microcontroller", "real-time"),
    "simulation": ("simulation", "hil", "sil", "dil", "virtual validation", "rapid prototyping"),
    "mechatronics": ("mechatronic", "mechatronics", "motor", "actuator", "sensor"),
    "controls": ("control engineering", "control systems", "controller"),
    "systems": ("systems engineering", "system architecture", "requirements engineering"),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _clamp(value: Any, lower: float = 0.0, upper: float = 100.0) -> float:
    return min(max(_safe_float(value, lower), lower), upper)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower()
    text = text.replace("_", " ").replace("/", " ").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9+#.\- ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _phrase_present(text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase)
    if not phrase:
        return False
    # Special handling for short technical tokens such as C++, C#, HIL, SIL.
    escaped = re.escape(phrase)
    return bool(re.search(rf"(?<![a-z0-9+#]){escaped}(?![a-z0-9+#])", text))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        value = value.strip()
        if value:
            yield value
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str) and item.strip():
                yield item.strip()


def _candidate_text(candidate_data: dict) -> str:
    parts = [
        str(candidate_data.get("professional_title", "")),
        str(candidate_data.get("professional_summary", "")),
    ]
    for field in ("technical_skills", "programming_languages", "tools", "methodologies", "industries", "leadership_experience"):
        parts.extend(_iter_strings(candidate_data.get(field)))
    for entry in candidate_data.get("employment_history", []) or []:
        if isinstance(entry, dict):
            parts.extend(_iter_strings(entry.get("technologies")))
            parts.extend(_iter_strings(entry.get("responsibilities")))
    return normalize_text(" ".join(parts))


def _family_hits(text: str, families: dict[str, tuple[str, ...]]) -> set[str]:
    hits = set()
    for family, variants in families.items():
        if any(_phrase_present(text, variant) for variant in variants):
            hits.add(family)
    return hits


def _title_tokens(value: Any) -> set[str]:
    tokens = {token.strip(".-") for token in normalize_text(value).split()}
    return {t for t in tokens if len(t) >= 2 and t not in TITLE_STOPWORDS}


def _title_score(candidate_data: dict, job_title: str) -> float:
    job_tokens = _title_tokens(job_title)
    if not job_tokens:
        return 0.0

    # Candidate role history is more useful than just the current title.
    candidate_titles = [str(candidate_data.get("professional_title", ""))]
    candidate_titles.extend(
        str(entry.get("role", ""))
        for entry in candidate_data.get("employment_history", []) or []
        if isinstance(entry, dict)
    )

    best = 0.0
    for title in candidate_titles:
        cand_tokens = _title_tokens(title)
        if not cand_tokens:
            continue
        overlap = len(cand_tokens & job_tokens)
        if not overlap:
            continue
        # Dice coefficient is less punitive when one title contains extra qualifiers.
        score = (2.0 * overlap / (len(cand_tokens) + len(job_tokens))) * 100.0
        best = max(best, score)

    # Role-family reinforcement catches titles like "Function Developer" vs
    # "Embedded Software Engineer" when the body clearly indicates embedded work.
    joined = normalize_text(f"{job_title} {_candidate_text(candidate_data)}")
    job_low = normalize_text(job_title)
    if any(k in job_low for k in ("embedded", "firmware", "autosar")) and "embedded" in joined:
        best = max(best, 72.0)
    if any(k in job_low for k in ("system", "systems")) and "systems" in joined:
        best = max(best, 65.0)
    if "simulation" in job_low and "simulation" in joined:
        best = max(best, 72.0)
    if "control" in job_low and "control" in joined:
        best = max(best, 72.0)
    return _clamp(best)


def _technical_score(candidate_text: str, job_text: str) -> tuple[float, list[str]]:
    candidate_hits = _family_hits(candidate_text, TERM_FAMILIES)
    job_hits = _family_hits(job_text, TERM_FAMILIES)
    matched = sorted(candidate_hits & job_hits)
    if not job_hits:
        unrelated_markers = (
            "java", "spring boot", "frontend", "backend", "kubernetes", "react web",
            "accounting", "bookkeeping", "nursing", "sales manager", "marketing",
        )
        if any(marker in job_text for marker in unrelated_markers):
            return 12.0, matched
        return 38.0, matched  # sparse advertisement: keep reviewable, but not artificially strong

    coverage = len(matched) / len(job_hits)
    # Evidence curve: 2-3 genuine families should already make a job worth review.
    evidence = min(len(matched) / 6.0, 1.0)
    score = (coverage * 70.0) + (evidence * 30.0)
    return _clamp(score), matched


def _domain_score(candidate_text: str, job_text: str) -> tuple[float, list[str]]:
    candidate_domains = _family_hits(candidate_text, DOMAIN_FAMILIES)
    job_domains = _family_hits(job_text, DOMAIN_FAMILIES)
    matched = sorted(candidate_domains & job_domains)
    if not job_domains:
        unrelated_markers = (
            "e-commerce", "web application", "accounting", "bookkeeping",
            "nursing", "sales", "marketing", "finance",
        )
        if any(marker in job_text for marker in unrelated_markers):
            return 15.0, matched
        return 40.0, matched
    return _clamp((len(matched) / len(job_domains)) * 100.0), matched


def _seniority_score(candidate_data: dict, job_text: str) -> float:
    low = normalize_text(job_text)
    leadership = bool(candidate_data.get("leadership_experience"))
    # The approved profile contains 9+ years; also infer experience breadth from history.
    summary = normalize_text(candidate_data.get("professional_summary", ""))
    experienced = bool(re.search(r"\b([6-9]|[1-9][0-9])\+? years\b", summary)) or len(candidate_data.get("employment_history", []) or []) >= 4

    if any(term in low for term in ("principal", "lead engineer", "team lead", "architect")):
        return 90.0 if leadership else (70.0 if experienced else 40.0)
    if "senior" in low:
        return 90.0 if experienced else 55.0
    if any(term in low for term in ("junior", "graduate", "working student", "intern")):
        return 35.0 if experienced else 80.0
    return 80.0 if experienced else 65.0


def initial_candidate_fit_breakdown(candidate_data: dict, job_title: str, job_description: str) -> dict[str, Any]:
    """Return explainable first-pass fit components and matched signal families."""
    if not isinstance(candidate_data, dict) or not candidate_data:
        return {"score": 0.0, "technical": 0.0, "title": 0.0, "seniority": 0.0, "domain": 0.0, "matched_technical_families": [], "matched_domain_families": []}

    candidate_text = _candidate_text(candidate_data)
    job_text = normalize_text(f"{job_title} {job_description}")
    if not job_text:
        return {"score": 0.0, "technical": 0.0, "title": 0.0, "seniority": 0.0, "domain": 0.0, "matched_technical_families": [], "matched_domain_families": []}

    technical, technical_hits = _technical_score(candidate_text, job_text)
    title = _title_score(candidate_data, job_title)
    seniority = _seniority_score(candidate_data, job_text)
    domain, domain_hits = _domain_score(candidate_text, job_text)

    # Week 6 refinement requested weighting.
    score = technical * 0.45 + title * 0.25 + seniority * 0.15 + domain * 0.15
    return {
        "score": round(_clamp(score), 1),
        "technical": round(technical, 1),
        "title": round(title, 1),
        "seniority": round(seniority, 1),
        "domain": round(domain, 1),
        "matched_technical_families": technical_hits,
        "matched_domain_families": domain_hits,
    }


def initial_candidate_fit_score(candidate_data: dict, job_title: str, job_description: str) -> float:
    return float(initial_candidate_fit_breakdown(candidate_data, job_title, job_description)["score"])


def location_score(distance_km: float | None, maximum_radius_km: float = 50.0) -> float:
    if distance_km is None:
        return 0.0
    distance = max(_safe_float(distance_km), 0.0)
    radius = max(_safe_float(maximum_radius_km, 50.0), 1.0)
    if distance >= radius:
        return 0.0
    return _clamp((1.0 - (distance / radius)) * 100.0)


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
    """Overall discovery score: location 25%, company 20%, salary 30%, fit 25%."""
    geo_score = location_score(distance_km, maximum_radius_km)
    company_score = _clamp(company_size_score(company_size))
    pay_score = _clamp(salary_score(
        published_salary_min, published_salary_max,
        estimated_salary_min, estimated_salary_max, minimum_salary,
    ))
    fit_score = _clamp(initial_fit_score)
    score = geo_score * 0.25 + company_score * 0.20 + pay_score * 0.30 + fit_score * 0.25
    return round(_clamp(score), 1)
