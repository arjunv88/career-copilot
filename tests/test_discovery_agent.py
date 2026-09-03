from dotenv import load_dotenv

from discovery.agent import (
    discover_jobs,
)

from scrapers.sources.arbeitnow import (
    ArbeitnowSource,
)

from scrapers.sources.ba_jobs import (
    BAJobsSource,
)

from scrapers.sources.jooble import (
    JoobleSource,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# TEST CANDIDATE
# ============================================================

CANDIDATE_DATA = {

    "professional_summary": (
        "Senior embedded software engineer "
        "with experience in automotive "
        "software development, embedded "
        "systems, C++, Python and AUTOSAR."
    ),

    "skills": [
        "C++",
        "Python",
        "AUTOSAR",
        "Embedded Systems",
        "Automotive Software",
        "CMake",
        "Git",
        "CI/CD",
    ],

    "technical_skills": [
        "C++",
        "Python",
        "AUTOSAR",
        "CMake",
        "Git",
        "Jenkins",
        "CAN",
        "LIN",
        "Ethernet",
        "Matlab",
        "Simulink",
    ],

    "experience": [
        (
            "Embedded automotive software "
            "development"
        ),
        (
            "Function development for "
            "safety-critical systems"
        ),
        (
            "Software integration and "
            "continuous integration"
        ),
    ],
}


# ============================================================
# TEST
# ============================================================

def test_discovery_agent_combines_all_sources():

    print()
    print(
        "========================================"
    )
    print(
        "Career Copilot Discovery Agent Test"
    )
    print(
        "========================================"
    )


    # --------------------------------------------------------
    # 1. Create all three real data sources
    # --------------------------------------------------------

    arbeitnow_source = (
        ArbeitnowSource(
            max_pages=1
        )
    )

    ba_source = (
        BAJobsSource(
            max_results=5,
            load_details=True,
        )
    )

    jooble_source = (
        JoobleSource(
            max_results=5
        )
    )


    sources = [
        arbeitnow_source,
        ba_source,
        jooble_source,
    ]


    # --------------------------------------------------------
    # 2. Run all three through the discovery agent
    # --------------------------------------------------------

    jobs = discover_jobs(

        sources=sources,

        candidate_data=(
            CANDIDATE_DATA
        ),

        keywords=(
            "Embedded Software Engineer"
        ),

        locations=[
            "Stuttgart",
        ],

        radius_km=50.0,

        minimum_salary=80000,
    )


    # --------------------------------------------------------
    # 3. Basic integration assertions
    # --------------------------------------------------------

    assert isinstance(
        jobs,
        list,
    )


    print()
    print(
        "Approved jobs:",
        len(jobs),
    )


    # --------------------------------------------------------
    # 4. Validate every returned job
    # --------------------------------------------------------

    for job in jobs:

        assert job.job_id

        assert job.title

        assert job.company

        assert job.location

        assert job.url


        assert (
            job.discovery_score
            >= 0.0
        )


        assert (
            job.initial_fit_score
            >= 0.0
        )


    # --------------------------------------------------------
    # 5. Verify descending ranking
    # --------------------------------------------------------

    scores = [

        job.discovery_score

        for job in jobs
    ]


    assert scores == sorted(
        scores,
        reverse=True,
    )


    # --------------------------------------------------------
    # 6. Check deduplication
    # --------------------------------------------------------

    dedupe_keys = [

        (
            job.company
            .strip()
            .lower(),

            job.title
            .strip()
            .lower(),

            job.location
            .strip()
            .lower(),
        )

        for job in jobs
    ]


    assert (
        len(dedupe_keys)
        ==
        len(set(dedupe_keys))
    )


    # --------------------------------------------------------
    # 7. Display results
    # --------------------------------------------------------

    print()
    print(
        "========================================"
    )
    print(
        "Approved discovery results"
    )
    print(
        "========================================"
    )


    for index, job in enumerate(
        jobs,
        start=1,
    ):

        print()
        print(
            f"{index}. {job.title}"
        )

        print(
            "Company:",
            job.company,
        )

        print(
            "Location:",
            job.location,
        )

        print(
            "Source:",
            job.source,
        )

        print(
            "Nearest major city:",
            job.nearest_major_city,
        )

        print(
            "Distance:",
            job.distance_to_major_city_km,
        )

        print(
            "Candidate fit:",
            round(
                job.initial_fit_score,
                1,
            ),
        )

        print(
            "Discovery score:",
            job.discovery_score,
        )

        print(
            "Published salary:",
            job.published_salary_min,
            "-",
            job.published_salary_max,
        )

        print(
            "Estimated salary:",
            job.estimated_salary_min,
            "-",
            job.estimated_salary_max,
        )

        print(
            "URL:",
            job.url,
        )


    print()
    print(
        "========================================"
    )

    print(
        "Discovery agent integration: PASS"
    )

    print(
        "========================================"
    )