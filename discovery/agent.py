"""
Career Copilot - Week 5 multi-source discovery agent.

Responsibilities:
  1. Query enabled job sources.
  2. Continue gracefully if one source/location fails.
  3. Combine and de-duplicate results across sources.
  4. Apply geography, company-size and salary hard filters.
  5. Calculate lightweight candidate fit and discovery score.
  6. Return jobs sorted from most to least promising.

The detailed AI job parser and C++ compatibility engine remain downstream.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from typing import Any

from discovery.geography import analyse_job_location
from discovery.filters import company_size_allowed
from discovery.salary import salary_is_promising
from discovery.ranking import (
    initial_candidate_fit_score,
    initial_candidate_fit_breakdown,
    calculate_discovery_score,
)


LOGGER = logging.getLogger(__name__)

# Keeps the public discover_jobs() return type unchanged while still making
# source failures inspectable by tests/UI code if desired.
_LAST_DISCOVERY_ERRORS: list[str] = []
_LAST_DISCOVERY_STATS: dict[str, dict[str, int]] = {}

_COMPANY_SUFFIXES = {
    "ag",
    "gmbh",
    "gmbh & co kg",
    "gmbh co kg",
    "kg",
    "se",
    "ug",
    "mbh",
}


def get_last_discovery_errors() -> list[str]:
    """Return source/job errors collected during the most recent run."""
    return list(_LAST_DISCOVERY_ERRORS)


def get_last_discovery_stats() -> dict[str, dict[str, int]]:
    """Return a copy of per-source discovery diagnostics for the latest run."""
    return {name: dict(values) for name, values in _LAST_DISCOVERY_STATS.items()}


def _source_stats(source_name: str) -> dict[str, int]:
    return _LAST_DISCOVERY_STATS.setdefault(
        source_name,
        {
            "retrieved": 0,
            "approved": 0,
            "rejected_geography": 0,
            "rejected_company_size": 0,
            "rejected_salary": 0,
            "rejected_invalid": 0,
            "errors": 0,
        },
    )


def _record_error(
    message: str,
) -> None:
    """Record and log a recoverable discovery error."""

    _LAST_DISCOVERY_ERRORS.append(
        message
    )
    LOGGER.warning(
        message
    )


def normalize_dedupe_value(
    value: Any,
) -> str:
    """
    Normalize text used for cross-source de-duplication.

    This is stronger than a simple lowercase/strip and handles punctuation,
    repeated whitespace and common German legal suffix formatting.
    """

    if value is None:
        return ""

    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(
        r"[^a-z0-9+#]+",
        " ",
        text,
    )
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _normalize_company_for_dedupe(
    value: Any,
) -> str:
    """Normalize company names while removing common legal-form suffixes."""

    normalized = normalize_dedupe_value(
        value
    )

    if not normalized:
        return ""

    # Remove legal suffixes only from the end.  This improves matching of
    # "Example GmbH" vs "Example" without over-normalizing names internally.
    changed = True

    while changed:
        changed = False

        for suffix in sorted(
            _COMPANY_SUFFIXES,
            key=len,
            reverse=True,
        ):
            suffix_normalized = normalize_dedupe_value(
                suffix
            )

            if normalized == suffix_normalized:
                break

            marker = (
                " "
                + suffix_normalized
            )

            if normalized.endswith(
                marker
            ):
                normalized = normalized[
                    :-len(marker)
                ].strip()
                changed = True
                break

    return normalized


def _job_attr(
    job: Any,
    name: str,
    default: Any = None,
) -> Any:
    """Read a field from either a Pydantic-like object or dictionary."""

    if isinstance(
        job,
        dict,
    ):
        return job.get(
            name,
            default,
        )

    return getattr(
        job,
        name,
        default,
    )


def _set_job_attr(
    job: Any,
    name: str,
    value: Any,
) -> None:
    """Set a field on a mutable job object/dictionary."""

    if isinstance(
        job,
        dict,
    ):
        job[name] = value
        return

    setattr(
        job,
        name,
        value,
    )


def _is_valid_job(
    job: Any,
) -> bool:
    """
    Require the minimum data needed by discovery.

    URL is not mandatory here because some sources may provide a valid job
    object whose external URL is unavailable; title and location are the
    essential fields for ranking/geography.
    """

    if job is None:
        return False

    title = str(
        _job_attr(
            job,
            "title",
            "",
        )
        or ""
    ).strip()

    location = str(
        _job_attr(
            job,
            "location",
            "",
        )
        or ""
    ).strip()

    return bool(
        title
        and location
    )


def _dedupe_key(
    job: Any,
) -> tuple[str, str, str]:
    """Build a cross-source de-duplication key."""

    company = _normalize_company_for_dedupe(
        _job_attr(
            job,
            "company",
            "",
        )
    )

    title = normalize_dedupe_value(
        _job_attr(
            job,
            "title",
            "",
        )
    )

    location = normalize_dedupe_value(
        _job_attr(
            job,
            "location",
            "",
        )
    )

    return (
        company,
        title,
        location,
    )


def _job_quality(
    job: Any,
) -> tuple[int, int, int]:
    """
    Rank duplicate records by information richness.

    Prefer:
      1. longer description
      2. salary information
      3. usable URL

    This lets, for example, a richer BA record replace a thin aggregator
    snippet for the same vacancy.
    """

    description = str(
        _job_attr(
            job,
            "description",
            "",
        )
        or ""
    ).strip()

    salary_fields = (
        "published_salary_min",
        "published_salary_max",
        "estimated_salary_min",
        "estimated_salary_max",
    )

    salary_count = sum(
        1
        for field_name in salary_fields
        if _job_attr(
            job,
            field_name,
            None,
        )
        is not None
    )

    url = str(
        _job_attr(
            job,
            "url",
            "",
        )
        or ""
    ).strip()

    return (
        len(description),
        salary_count,
        1 if url else 0,
    )


def _append_duplicate_source_metadata(
    kept_job: Any,
    other_job: Any,
) -> None:
    """
    Store duplicate-source provenance in metadata when possible.

    Failure to mutate metadata must never break discovery.
    """

    kept_source = str(
        _job_attr(
            kept_job,
            "source",
            "",
        )
        or ""
    ).strip()

    other_source = str(
        _job_attr(
            other_job,
            "source",
            "",
        )
        or ""
    ).strip()

    sources = {
        source
        for source in (
            kept_source,
            other_source,
        )
        if source
    }

    if not sources:
        return

    metadata = _job_attr(
        kept_job,
        "metadata",
        None,
    )

    if not isinstance(
        metadata,
        dict,
    ):
        metadata = {}

    existing_sources = metadata.get(
        "duplicate_sources",
        [],
    )

    if isinstance(
        existing_sources,
        list,
    ):
        sources.update(
            str(item)
            for item in existing_sources
            if str(item).strip()
        )

    metadata[
        "duplicate_sources"
    ] = sorted(
        sources
    )

    try:
        _set_job_attr(
            kept_job,
            "metadata",
            metadata,
        )
    except Exception:
        # Metadata enrichment is optional.
        pass


def deduplicate_jobs(
    jobs: Iterable[Any],
) -> list[Any]:
    """
    Remove cross-source duplicates while preserving the richer record.

    Jobs with an empty company name are still deduplicated using title and
    location.  This is imperfect but safer than showing obvious duplicates.
    """

    unique_jobs: dict[
        tuple[str, str, str],
        Any,
    ] = {}

    passthrough_jobs: list[Any] = []

    for job in jobs:
        if not _is_valid_job(
            job
        ):
            continue

        key = _dedupe_key(
            job
        )

        # If title/location normalization somehow produces no usable key,
        # retain the record rather than accidentally collapsing unrelated
        # jobs together.
        if not key[1] or not key[2]:
            passthrough_jobs.append(
                job
            )
            continue

        existing = unique_jobs.get(
            key
        )

        if existing is None:
            unique_jobs[
                key
            ] = job
            continue

        if _job_quality(
            job
        ) > _job_quality(
            existing
        ):
            _append_duplicate_source_metadata(
                job,
                existing,
            )
            unique_jobs[
                key
            ] = job
        else:
            _append_duplicate_source_metadata(
                existing,
                job,
            )

    return (
        list(
            unique_jobs.values()
        )
        + passthrough_jobs
    )


def _coerce_source_jobs(
    result: Any,
    source_name: str,
) -> list[Any]:
    """Convert a source result to a safe job list."""

    if result is None:
        return []

    if isinstance(
        result,
        list,
    ):
        return [
            job
            for job in result
            if _is_valid_job(job)
        ]

    if isinstance(
        result,
        tuple,
    ):
        return [
            job
            for job in result
            if _is_valid_job(job)
        ]

    _record_error(
        f"{source_name} returned an unsupported result type "
        f"({type(result).__name__}); source result was ignored."
    )

    return []


def _source_name(
    source: Any,
) -> str:
    """Return a readable source name for diagnostics."""

    explicit_name = getattr(
        source,
        "SOURCE_NAME",
        None,
    )

    if explicit_name:
        return str(
            explicit_name
        )

    return source.__class__.__name__


def _collect_from_source(
    source: Any,
    keywords: str,
    locations: list[str],
) -> list[Any]:
    """
    Collect jobs from one source without allowing its failures to propagate.

    A source may optionally define:
        location_scoped = False

    That is useful for global feeds such as Arbeitnow that ignore the
    location argument; such a source will then be queried only once.
    Existing source classes that do not define the attribute retain the
    current behavior (one call per selected city).
    """

    source_name = _source_name(
        source
    )
    _source_stats(source_name)

    collected: list[Any] = []

    if hasattr(
        source,
        "search_jobs",
    ):
        location_scoped = bool(
            getattr(
                source,
                "location_scoped",
                True,
            )
        )

        query_locations = (
            locations
            if location_scoped
            else locations[:1]
        )

        for location in query_locations:
            try:
                result = source.search_jobs(
                    keywords,
                    location,
                )

                valid_jobs = _coerce_source_jobs(result, source_name)
                _source_stats(source_name)["retrieved"] += len(valid_jobs)
                collected.extend(valid_jobs)

            except Exception as error:
                _source_stats(source_name)["errors"] += 1
                _record_error(
                    f"{source_name} failed for location '{location}': {error}"
                )

        return collected

    if callable(source):
        try:
            result = source(
                keywords,
                locations,
            )

            valid_jobs = _coerce_source_jobs(result, source_name)
            _source_stats(source_name)["retrieved"] += len(valid_jobs)
            collected.extend(valid_jobs)

        except Exception as error:
            _source_stats(source_name)["errors"] += 1
            _record_error(f"{source_name} failed: {error}")

        return collected

    _record_error(
        f"{source_name} was ignored because it does not implement "
        "search_jobs() and is not callable."
    )

    return collected


def _source_name_from_job(job: Any) -> str:
    name = str(_job_attr(job, "source", "Unknown") or "Unknown").strip()
    return name or "Unknown"


def enrich_job(
    job: Any,
    candidate_data: dict,
    location_analysis: dict,
    radius_km: float = 50.0,
    minimum_salary: float = 80000,
) -> Any:
    """Apply geography metadata and calculate ranking fields for one job."""

    nearest_major_city = (
        location_analysis.get(
            "nearest_major_city",
            "",
        )
        or ""
    )

    distance_km = (
        location_analysis.get(
            "distance_km"
        )
    )

    _set_job_attr(
        job,
        "nearest_major_city",
        nearest_major_city,
    )

    _set_job_attr(
        job,
        "distance_to_major_city_km",
        distance_km,
    )

    fit_breakdown = initial_candidate_fit_breakdown(
        candidate_data,
        str(_job_attr(job, "title", "") or ""),
        str(_job_attr(job, "description", "") or ""),
    )
    initial_fit = float(fit_breakdown["score"])
    _set_job_attr(job, "initial_fit_score", initial_fit)

    metadata = _job_attr(job, "metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["candidate_fit_breakdown"] = fit_breakdown
    _set_job_attr(job, "metadata", metadata)

    discovery_score = (
        calculate_discovery_score(
            distance_km=distance_km,
            company_size=str(
                _job_attr(
                    job,
                    "company_size",
                    "Unknown",
                )
                or "Unknown"
            ),
            published_salary_min=_job_attr(
                job,
                "published_salary_min",
                None,
            ),
            published_salary_max=_job_attr(
                job,
                "published_salary_max",
                None,
            ),
            estimated_salary_min=_job_attr(
                job,
                "estimated_salary_min",
                None,
            ),
            estimated_salary_max=_job_attr(
                job,
                "estimated_salary_max",
                None,
            ),
            initial_fit_score=initial_fit,
            maximum_radius_km=radius_km,
            minimum_salary=minimum_salary,
        )
    )

    _set_job_attr(
        job,
        "discovery_score",
        discovery_score,
    )

    return job


def _validate_discovery_inputs(
    sources: Any,
    candidate_data: Any,
    keywords: Any,
    locations: Any,
    radius_km: Any,
    minimum_salary: Any,
) -> tuple[
    list[Any],
    dict,
    str,
    list[str],
    float,
    float,
]:
    """Validate and normalize the public discover_jobs() inputs."""

    if not isinstance(
        candidate_data,
        dict,
    ):
        raise TypeError(
            "candidate_data must be a dictionary."
        )

    if sources is None:
        normalized_sources: list[Any] = []
    else:
        try:
            normalized_sources = list(
                sources
            )
        except TypeError as error:
            raise TypeError(
                "sources must be an iterable of job-source objects."
            ) from error

    if locations is None:
        normalized_locations: list[str] = []
    else:
        try:
            normalized_locations = [
                str(location).strip()
                for location in locations
                if str(location).strip()
            ]
        except TypeError as error:
            raise TypeError(
                "locations must be an iterable of city/location strings."
            ) from error

    normalized_keywords = str(
        keywords or ""
    ).strip()

    if not normalized_keywords:
        raise ValueError(
            "keywords must contain at least one non-whitespace character."
        )

    try:
        normalized_radius = float(
            radius_km
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "radius_km must be numeric."
        ) from error

    if normalized_radius <= 0:
        raise ValueError(
            "radius_km must be greater than zero."
        )

    try:
        normalized_salary = float(
            minimum_salary
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "minimum_salary must be numeric."
        ) from error

    if normalized_salary < 0:
        raise ValueError(
            "minimum_salary cannot be negative."
        )

    return (
        normalized_sources,
        candidate_data,
        normalized_keywords,
        normalized_locations,
        normalized_radius,
        normalized_salary,
    )


def discover_jobs(
    sources,
    candidate_data: dict,
    keywords: str,
    locations: list[str],
    radius_km: float = 50.0,
    minimum_salary: float = 80000,
):
    """
    Discover, filter, enrich and rank jobs.

    Source failures and malformed individual jobs are recoverable: they are
    logged/recorded and discovery continues with the remaining sources/jobs.
    Invalid top-level API inputs raise clear exceptions because they indicate
    a programming/configuration error rather than an external-source failure.
    """

    _LAST_DISCOVERY_ERRORS.clear()
    _LAST_DISCOVERY_STATS.clear()

    (
        normalized_sources,
        candidate_data,
        keywords,
        normalized_locations,
        radius_km,
        minimum_salary,
    ) = _validate_discovery_inputs(
        sources,
        candidate_data,
        keywords,
        locations,
        radius_km,
        minimum_salary,
    )

    if not normalized_sources:
        return []

    if not normalized_locations:
        return []

    collected_jobs: list[Any] = []

    for source in normalized_sources:
        collected_jobs.extend(
            _collect_from_source(
                source,
                keywords,
                normalized_locations,
            )
        )

    if not collected_jobs:
        return []

    unique_jobs = deduplicate_jobs(
        collected_jobs
    )

    approved_jobs: list[Any] = []

    # Avoid repeated geography calls for identical location strings during
    # one discovery run, in addition to any persistent cache in geography.py.
    location_cache: dict[
        str,
        dict | None,
    ] = {}

    for job in unique_jobs:
        try:
            location = str(
                _job_attr(
                    job,
                    "location",
                    "",
                )
                or ""
            ).strip()

            if not location:
                continue

            cache_key = normalize_dedupe_value(
                location
            )

            if cache_key not in location_cache:
                try:
                    location_cache[
                        cache_key
                    ] = analyse_job_location(
                        location,
                        radius_km,
                    )
                except Exception as error:
                    location_cache[
                        cache_key
                    ] = None
                    _record_error(
                        f"Geography lookup failed for '{location}': {error}"
                    )

            location_analysis = location_cache.get(
                cache_key
            )

            if not isinstance(
                location_analysis,
                dict,
            ):
                continue

            if not bool(location_analysis.get("within_radius", False)):
                _source_stats(_source_name_from_job(job))["rejected_geography"] += 1
                continue

            company_size = str(
                _job_attr(
                    job,
                    "company_size",
                    "Unknown",
                )
                or "Unknown"
            )

            try:
                size_allowed = company_size_allowed(
                    company_size
                )
            except Exception as error:
                _record_error(
                    f"Company-size evaluation failed for "
                    f"'{_job_attr(job, 'title', 'Unknown job')}': {error}"
                )
                continue

            if not size_allowed:
                _source_stats(_source_name_from_job(job))["rejected_company_size"] += 1
                continue

            try:
                salary_allowed = salary_is_promising(
                    _job_attr(
                        job,
                        "published_salary_min",
                        None,
                    ),
                    _job_attr(
                        job,
                        "published_salary_max",
                        None,
                    ),
                    _job_attr(
                        job,
                        "estimated_salary_min",
                        None,
                    ),
                    _job_attr(
                        job,
                        "estimated_salary_max",
                        None,
                    ),
                    minimum_salary,
                )
            except Exception as error:
                _record_error(
                    f"Salary evaluation failed for "
                    f"'{_job_attr(job, 'title', 'Unknown job')}': {error}"
                )
                continue

            if not salary_allowed:
                _source_stats(_source_name_from_job(job))["rejected_salary"] += 1
                continue

            approved_jobs.append(
                enrich_job(
                    job=job,
                    candidate_data=candidate_data,
                    location_analysis=location_analysis,
                    radius_km=radius_km,
                    minimum_salary=minimum_salary,
                )
            )
            _source_stats(_source_name_from_job(job))["approved"] += 1

        except Exception as error:
            # One malformed job must never abort all discovery results.
            _record_error(
                f"Job enrichment failed for "
                f"'{_job_attr(job, 'title', 'Unknown job')}': {error}"
            )
            continue

    approved_jobs.sort(
        key=lambda job: float(
            _job_attr(
                job,
                "discovery_score",
                0.0,
            )
            or 0.0
        ),
        reverse=True,
    )

    return approved_jobs
