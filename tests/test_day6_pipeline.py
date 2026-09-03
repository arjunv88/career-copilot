from pathlib import Path

import discovery.agent as agent
import storage.discovered_jobs as storage

from scrapers.models import (
    DiscoveredJob,
)


# ============================================================
# DUMMY CANDIDATE
# ============================================================

DUMMY_CANDIDATE = {

    "professional_summary":
        "Senior embedded software engineer "
        "with C++ and Python experience",

    "skills": [
        "C++",
        "Python",
        "AUTOSAR",
        "Embedded Systems",
    ],

    "technical_skills": [
        "CMake",
        "Git",
        "CI/CD",
    ],

    "experience": [
        "Embedded software development",
        "Automotive software",
    ],
}


# ============================================================
# DUMMY JOB SOURCE
# ============================================================

class DummyJobSource:

    def search_jobs(
        self,
        keywords: str,
        location: str,
    ):

        # Return jobs only once.
        # Otherwise every requested location
        # would produce the same dummy data.

        if location != "Stuttgart":
            return []

        return [

            # ------------------------------------------------
            # GOOD JOB 1
            # ------------------------------------------------

            DiscoveredJob(

                job_id="job-001",

                title=(
                    "Senior Embedded "
                    "Software Engineer"
                ),

                company="Bosch",

                location="Stuttgart",

                url=(
                    "https://example.com/"
                    "job-001"
                ),

                description=(
                    "Develop embedded "
                    "software using C++ "
                    "Python AUTOSAR and "
                    "CMake."
                ),

                source="Dummy",

                company_size="Large",

                published_salary_min=90000,

                published_salary_max=100000,
            ),


            # ------------------------------------------------
            # DUPLICATE OF JOB 1
            # ------------------------------------------------

            DiscoveredJob(

                job_id="job-001-duplicate",

                title=(
                    "Senior Embedded "
                    "Software Engineer"
                ),

                company="Bosch",

                location="Stuttgart",

                url=(
                    "https://example.com/"
                    "job-001-duplicate"
                ),

                description=(
                    "Duplicate job"
                ),

                source="Dummy",

                company_size="Large",

                published_salary_min=90000,

                published_salary_max=100000,
            ),


            # ------------------------------------------------
            # GOOD JOB 2
            # UNKNOWN SALARY IS ALLOWED
            # ------------------------------------------------

            DiscoveredJob(

                job_id="job-002",

                title=(
                    "Embedded C++ Developer"
                ),

                company="Siemens",

                location="Munich",

                url=(
                    "https://example.com/"
                    "job-002"
                ),

                description=(
                    "Embedded C++ software "
                    "development with CMake "
                    "and Python."
                ),

                source="Dummy",

                company_size="Large",

                published_salary_min=None,

                published_salary_max=None,

                estimated_salary_min=None,

                estimated_salary_max=None,
            ),


            # ------------------------------------------------
            # REJECTED: SMALL COMPANY
            # ------------------------------------------------

            DiscoveredJob(

                job_id="job-003",

                title="Python Developer",

                company="Tiny Startup",

                location="Berlin",

                url=(
                    "https://example.com/"
                    "job-003"
                ),

                description=(
                    "Python development."
                ),

                source="Dummy",

                company_size="Small",

                published_salary_min=90000,

                published_salary_max=100000,
            ),


            # ------------------------------------------------
            # REJECTED: LOW SALARY
            # ------------------------------------------------

            DiscoveredJob(

                job_id="job-004",

                title=(
                    "Embedded Developer"
                ),

                company="Example GmbH",

                location="Hamburg",

                url=(
                    "https://example.com/"
                    "job-004"
                ),

                description=(
                    "Embedded systems."
                ),

                source="Dummy",

                company_size="Large",

                published_salary_min=60000,

                published_salary_max=65000,
            ),


            # ------------------------------------------------
            # REJECTED: TOO FAR FROM MAJOR CITY
            # ------------------------------------------------

            DiscoveredJob(

                job_id="job-005",

                title=(
                    "C++ Software Engineer"
                ),

                company="Far Away GmbH",

                location="Remote Village",

                url=(
                    "https://example.com/"
                    "job-005"
                ),

                description=(
                    "C++ development."
                ),

                source="Dummy",

                company_size="Large",

                published_salary_min=90000,

                published_salary_max=95000,
            ),
        ]


# ============================================================
# FAKE GEOGRAPHY
#
# IMPORTANT:
# We do NOT call OpenStreetMap during this test.
#
# This makes the test:
# - fast
# - deterministic
# - usable offline
# ============================================================

def fake_analyse_job_location(
    location: str,
    radius_km: float = 50.0,
):

    locations = {

        "Stuttgart": {
            "city": "Stuttgart",
            "distance": 0.0,
        },

        "Munich": {
            "city": "Munich",
            "distance": 0.0,
        },

        "Berlin": {
            "city": "Berlin",
            "distance": 0.0,
        },

        "Hamburg": {
            "city": "Hamburg",
            "distance": 0.0,
        },

        "Remote Village": {
            "city": "Stuttgart",
            "distance": 120.0,
        },
    }

    result = locations.get(
        location
    )

    if result is None:

        return {
            "location": location,
            "latitude": None,
            "longitude": None,
            "nearest_major_city": "",
            "distance_km": None,
            "within_radius": False,
        }

    distance = (
        result["distance"]
    )

    return {
        "location": location,
        "latitude": 0.0,
        "longitude": 0.0,
        "nearest_major_city": (
            result["city"]
        ),
        "distance_km": distance,
        "within_radius": (
            distance <= radius_km
        ),
    }


# ============================================================
# TEST 1
# COMPLETE DISCOVERY PIPELINE
# ============================================================

def test_complete_discovery_pipeline(
    monkeypatch,
):

    print()
    print(
        "Testing complete "
        "discovery pipeline..."
    )

    # Replace real geography API
    # with our deterministic fake.

    monkeypatch.setattr(
        agent,
        "analyse_job_location",
        fake_analyse_job_location,
    )

    source = DummyJobSource()

    jobs = agent.discover_jobs(

        sources=[
            source
        ],

        candidate_data=(
            DUMMY_CANDIDATE
        ),

        keywords=(
            "embedded software"
        ),

        locations=[
            "Stuttgart",
            "Munich",
        ],

        radius_km=50.0,

        minimum_salary=80000,
    )


    # --------------------------------------------------------
    # Only Bosch + Siemens should survive.
    # --------------------------------------------------------

    assert len(jobs) == 2


    companies = {
        job.company
        for job in jobs
    }


    assert "Bosch" in companies

    assert "Siemens" in companies


    assert (
        "Tiny Startup"
        not in companies
    )

    assert (
        "Example GmbH"
        not in companies
    )

    assert (
        "Far Away GmbH"
        not in companies
    )


    # --------------------------------------------------------
    # Duplicate Bosch job should be removed.
    # --------------------------------------------------------

    bosch_jobs = [

        job
        for job in jobs

        if (
            job.company
            == "Bosch"
        )
    ]

    assert len(
        bosch_jobs
    ) == 1


    # --------------------------------------------------------
    # Geography enrichment should exist.
    # --------------------------------------------------------

    for job in jobs:

        assert (
            job.nearest_major_city
        )

        assert (
            job.distance_to_major_city_km
            is not None
        )


    # --------------------------------------------------------
    # Candidate fit score should be calculated.
    # --------------------------------------------------------

    for job in jobs:

        assert (
            job.initial_fit_score
            >= 0.0
        )


    # --------------------------------------------------------
    # Discovery score should be calculated.
    # --------------------------------------------------------

    for job in jobs:

        assert (
            job.discovery_score
            > 0.0
        )


    # --------------------------------------------------------
    # Results should be sorted high → low.
    # --------------------------------------------------------

    scores = [

        job.discovery_score
        for job in jobs
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


    print(
        "Complete discovery "
        "pipeline: PASS"
    )

    print()

    for job in jobs:

        print(
            f"{job.company:12} | "
            f"{job.title:35} | "
            f"Fit: "
            f"{job.initial_fit_score:5.1f} | "
            f"Discovery: "
            f"{job.discovery_score:5.1f}"
        )


# ============================================================
# TEST 2
# STORAGE ROUND TRIP
# ============================================================

def test_discovery_storage_round_trip(
    monkeypatch,
    tmp_path,
):

    print()
    print(
        "Testing discovered "
        "job persistence..."
    )


    monkeypatch.setattr(
        agent,
        "analyse_job_location",
        fake_analyse_job_location,
    )


    jobs = agent.discover_jobs(

        sources=[
            DummyJobSource()
        ],

        candidate_data=(
            DUMMY_CANDIDATE
        ),

        keywords=(
            "embedded software"
        ),

        locations=[
            "Stuttgart"
        ],

        radius_km=50.0,

        minimum_salary=80000,
    )


    # --------------------------------------------------------
    # Use temporary file.
    #
    # This prevents our test from touching:
    #
    # data/discovered_jobs.json
    # --------------------------------------------------------

    test_file = (
        tmp_path
        / "discovered_jobs.json"
    )


    monkeypatch.setattr(
        storage,
        "DISCOVERED_JOBS_FILE",
        test_file,
    )


    # --------------------------------------------------------
    # Convert Pydantic models → dictionaries.
    # --------------------------------------------------------

    serialized_jobs = [

        job.model_dump()

        for job in jobs
    ]


    storage.save_discovered_jobs(
        serialized_jobs
    )


    assert (
        test_file.exists()
    )


    loaded_jobs = (
        storage.load_discovered_jobs()
    )


    assert (
        len(loaded_jobs)
        == len(jobs)
    )


    assert (
        loaded_jobs[0][
            "company"
        ]
        == jobs[0].company
    )


    assert (
        loaded_jobs[0][
            "discovery_score"
        ]
        == jobs[0].discovery_score
    )


    print(
        "Storage round trip: PASS"
    )


# ============================================================
# TEST 3
# EMPTY SOURCE
# ============================================================

def test_empty_source(
    monkeypatch,
):

    class EmptySource:

        def search_jobs(
            self,
            keywords,
            location,
        ):

            return []


    monkeypatch.setattr(
        agent,
        "analyse_job_location",
        fake_analyse_job_location,
    )


    result = (
        agent.discover_jobs(

            sources=[
                EmptySource()
            ],

            candidate_data=(
                DUMMY_CANDIDATE
            ),

            keywords="embedded",

            locations=[
                "Stuttgart"
            ],
        )
    )


    assert result == []

    print()
    print(
        "Empty source handling: PASS"
    )