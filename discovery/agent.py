from discovery.geography import (
    analyse_job_location,
)

from discovery.filters import (
    company_size_allowed,
)

from discovery.salary import (
    salary_is_promising,
)

from discovery.ranking import (
    initial_candidate_fit_score,
    calculate_discovery_score,
)


def normalize_dedupe_value(
    value: str,
) -> str:

    if not value:
        return ""

    return (
        value
        .strip()
        .lower()
    )


def deduplicate_jobs(
    jobs,
):

    unique_jobs = {}

    for job in jobs:

        key = (
            normalize_dedupe_value(
                job.company
            ),
            normalize_dedupe_value(
                job.title
            ),
            normalize_dedupe_value(
                job.location
            ),
        )

        if key not in unique_jobs:
            unique_jobs[key] = job

    return list(
        unique_jobs.values()
    )


def enrich_job(
    job,
    candidate_data: dict,
    location_analysis: dict,
    radius_km: float = 50.0,
    minimum_salary: float = 80000,
):

    # -----------------------------------------
    # Geography enrichment
    # -----------------------------------------

    job.nearest_major_city = (
        location_analysis[
            "nearest_major_city"
        ]
    )

    job.distance_to_major_city_km = (
        location_analysis[
            "distance_km"
        ]
    )

    # -----------------------------------------
    # Candidate fit
    # -----------------------------------------

    job.initial_fit_score = (
        initial_candidate_fit_score(
            candidate_data,
            job.title,
            job.description,
        )
    )

    # -----------------------------------------
    # Discovery score
    # -----------------------------------------

    job.discovery_score = (
        calculate_discovery_score(
            distance_km=(
                job.distance_to_major_city_km
            ),
            company_size=(
                job.company_size
            ),
            published_salary_min=(
                job.published_salary_min
            ),
            published_salary_max=(
                job.published_salary_max
            ),
            estimated_salary_min=(
                job.estimated_salary_min
            ),
            estimated_salary_max=(
                job.estimated_salary_max
            ),
            initial_fit_score=(
                job.initial_fit_score
            ),
            maximum_radius_km=(
                radius_km
            ),
            minimum_salary=(
                minimum_salary
            ),
        )
    )

    return job


def discover_jobs(
    sources,
    candidate_data: dict,
    keywords: str,
    locations: list[str],
    radius_km: float = 50.0,
    minimum_salary: float = 80000,
):

    jobs = []

    # -----------------------------------------
    # Validate input
    # -----------------------------------------

    if not sources:
        return []

    if not locations:
        return []

    # -----------------------------------------
    # Collect jobs from every source
    # -----------------------------------------

    for source in sources:

        if hasattr(
            source,
            "search_jobs",
        ):

            for location in locations:

                source_jobs = (
                    source.search_jobs(
                        keywords,
                        location,
                    )
                )

                if source_jobs:
                    jobs.extend(
                        source_jobs
                    )

        elif callable(source):

            source_jobs = (
                source(
                    keywords,
                    locations,
                )
            )

            if source_jobs:
                jobs.extend(
                    source_jobs
                )

        else:

            raise TypeError(
                "Discovery source must "
                "implement search_jobs() "
                "or be callable."
            )

    # -----------------------------------------
    # Nothing returned by sources
    # -----------------------------------------

    if not jobs:
        return []

    # -----------------------------------------
    # Remove duplicates
    # -----------------------------------------

    unique_jobs = (
        deduplicate_jobs(
            jobs
        )
    )

    approved_jobs = []

    # -----------------------------------------
    # Filter + enrich jobs
    # -----------------------------------------

    for job in unique_jobs:

        # -------------------------------------
        # Geography
        # -------------------------------------

        location_analysis = (
            analyse_job_location(
                job.location,
                radius_km,
            )
        )

        location_allowed = (
            location_analysis[
                "within_radius"
            ]
        )

        # -------------------------------------
        # Company size
        # -------------------------------------

        size_allowed = (
            company_size_allowed(
                job.company_size
            )
        )

        # -------------------------------------
        # Salary
        # -------------------------------------

        salary_allowed = (
            salary_is_promising(
                job.published_salary_min,
                job.published_salary_max,
                job.estimated_salary_min,
                job.estimated_salary_max,
                minimum_salary,
            )
        )

        # -------------------------------------
        # Reject jobs that fail hard filters
        # -------------------------------------

        if not (
            location_allowed
            and size_allowed
            and salary_allowed
        ):
            continue

        # -------------------------------------
        # Enrich accepted job
        # -------------------------------------

        enriched_job = (
            enrich_job(
                job=job,
                candidate_data=(
                    candidate_data
                ),
                location_analysis=(
                    location_analysis
                ),
                radius_km=(
                    radius_km
                ),
                minimum_salary=(
                    minimum_salary
                ),
            )
        )

        approved_jobs.append(
            enriched_job
        )

    # -----------------------------------------
    # Highest discovery score first
    # -----------------------------------------

    approved_jobs.sort(
        key=lambda job:
            job.discovery_score,
        reverse=True,
    )

    return approved_jobs