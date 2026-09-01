from pydantic import BaseModel, Field


class DiscoveredJob(BaseModel):
    job_id: str

    title: str
    company: str
    location: str

    url: str
    description: str = ""

    source: str = ""
    posted_date: str = ""

    nearest_major_city: str = ""
    distance_to_major_city_km: float | None = None

    company_size: str = ""
    company_size_confidence: str = ""

    published_salary_min: float | None = None
    published_salary_max: float | None = None

    estimated_salary_min: float | None = None
    estimated_salary_max: float | None = None
    salary_confidence: str = ""

    initial_fit_score: float = 0.0
    discovery_score: float = 0.0

    metadata: dict = Field(
        default_factory=dict
    )