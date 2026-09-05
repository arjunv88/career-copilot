from scrapers.models import DiscoveredJob
import discovery.agent as agent


class GoodSource:
    SOURCE_NAME = "GoodSource"
    location_scoped = False

    def search_jobs(self, keywords, location):
        return [
            DiscoveredJob(
                job_id="1",
                title="Embedded Software Engineer",
                company="Example GmbH",
                location="Stuttgart",
                url="https://example.invalid/job",
                description="Embedded C++ AUTOSAR ISO 26262 software engineering role with Python and CAN.",
                source=self.SOURCE_NAME,
                company_size="Large",
            )
        ]


class EmptySource:
    SOURCE_NAME = "EmptySource"
    location_scoped = False

    def search_jobs(self, keywords, location):
        return []


class BadSource:
    SOURCE_NAME = "BadSource"
    location_scoped = False

    def search_jobs(self, keywords, location):
        raise RuntimeError("synthetic source failure")


def test_discovery_reports_zero_results_and_failures(monkeypatch):
    monkeypatch.setattr(
        agent,
        "analyse_job_location",
        lambda location, radius: {
            "within_radius": True,
            "nearest_major_city": "Stuttgart",
            "distance_km": 2.0,
        },
    )

    candidate = {
        "professional_title": "Embedded Systems Engineer",
        "professional_summary": "Embedded systems engineer with 9+ years of experience.",
        "technical_skills": ["C++", "AUTOSAR", "ISO 26262", "CAN"],
        "programming_languages": ["C++", "Python"],
        "tools": ["CMake"],
        "methodologies": ["ISO 26262"],
        "industries": ["Automotive", "Embedded Systems"],
        "employment_history": [],
        "leadership_experience": [],
    }

    jobs = agent.discover_jobs(
        [GoodSource(), EmptySource(), BadSource()],
        candidate,
        "Embedded Software Engineer",
        ["Stuttgart"],
        radius_km=50,
        minimum_salary=80000,
    )

    stats = agent.get_last_discovery_stats()
    assert len(jobs) == 1
    assert stats["GoodSource"]["retrieved"] == 1
    assert stats["GoodSource"]["approved"] == 1
    assert stats["EmptySource"]["retrieved"] == 0
    assert stats["EmptySource"]["errors"] == 0
    assert stats["BadSource"]["errors"] == 1
    assert agent.get_last_discovery_errors()
