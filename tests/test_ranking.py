from discovery.ranking import (
    calculate_discovery_score,
)


score = calculate_discovery_score(
    distance_km=10.0,
    company_size="Large",
    published_salary_min=85000,
    published_salary_max=95000,
    estimated_salary_min=None,
    estimated_salary_max=None,
    initial_fit_score=80.0,
)


print(
    "Discovery score:",
    score,
)