import json
from pathlib import Path

from discovery.ranking import initial_candidate_fit_breakdown, initial_candidate_fit_score


PROFILE = json.loads(Path("candidate_profile.json").read_text(encoding="utf-8"))


def test_relevant_embedded_role_ranks_well_above_unrelated_role():
    embedded = initial_candidate_fit_score(
        PROFILE,
        "Senior Embedded Software Engineer AUTOSAR",
        "Develop C++ embedded software for automotive ECUs using AUTOSAR, ISO 26262, CAN, CMake and CI/CD.",
    )
    unrelated = initial_candidate_fit_score(
        PROFILE,
        "Senior Java Backend Developer",
        "Build Spring Boot microservices with Java, Kubernetes, Kafka and PostgreSQL for e-commerce systems.",
    )
    assert embedded >= 65.0
    assert unrelated < embedded - 25.0


def test_breakdown_is_explainable_and_bounded():
    result = initial_candidate_fit_breakdown(
        PROFILE,
        "Simulation Engineer",
        "Real-time simulation, MATLAB/Simulink, dSPACE, HIL and control systems.",
    )
    assert 0 <= result["score"] <= 100
    for field in ("technical", "title", "seniority", "domain"):
        assert 0 <= result[field] <= 100
    assert result["matched_technical_families"]
