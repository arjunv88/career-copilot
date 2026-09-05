import os
import re
from hashlib import sha256

import os
from dotenv import load_dotenv

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

if not JOOBLE_API_KEY:
    raise RuntimeError(
        "JOOBLE_API_KEY is not configured."
    )

import requests

from scrapers.base import JobSource
from scrapers.models import DiscoveredJob


class JoobleSource(JobSource):

    SOURCE_NAME = "Jooble"

    BASE_URL = "https://de.jooble.org/api"

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 20,
    ):

        self.api_key = (
            api_key
            or os.getenv(
                "JOOBLE_API_KEY"
            )
        )

        self.max_results = max_results


    def search_jobs(
        self,
        keywords: str,
        location: str,
    ) -> list[DiscoveredJob]:

        if not self.api_key:

            raise RuntimeError(
                "JOOBLE_API_KEY is not configured."
            )

        url = (
            f"{self.BASE_URL}/"
            f"{self.api_key}"
        )

        # Jooble does not offer exactly
        # 50 km. We deliberately request
        # 80 km and let geography.py apply
        # the real 50 km Career Copilot rule.
        payload = {
            "keywords": keywords,
            "location": location,
            "radius": "80",
            "page": 1,
            "ResultOnPage": (
                self.max_results
            ),
            "SearchMode": 0,
            "companysearch": False,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        raw_jobs = data.get(
            "jobs",
            []
        )

        discovered_jobs = []

        for raw_job in raw_jobs:

            job = self._convert_job(
                raw_job
            )

            if job is not None:

                discovered_jobs.append(
                    job
                )

        return discovered_jobs


    def _convert_job(
        self,
        raw_job: dict,
    ) -> DiscoveredJob | None:

        title = str(
            raw_job.get(
                "title",
                ""
            )
        ).strip()

        company = str(
            raw_job.get(
                "company",
                ""
            )
        ).strip()

        location = str(
            raw_job.get(
                "location",
                ""
            )
        ).strip()

        url = str(
            raw_job.get(
                "link",
                ""
            )
        ).strip()


        if not title:
            return None

        if not location:
            return None

        if not url:
            return None


        salary_text = str(
            raw_job.get(
                "salary",
                ""
            )
        )

        (
            salary_min,
            salary_max,
        ) = self._parse_salary(
            salary_text
        )


        raw_id = raw_job.get(
            "id"
        )

        if raw_id:

            job_id = (
                f"jooble-{raw_id}"
            )

        else:

            job_id = (
                self._create_job_id(
                    title,
                    company,
                    location,
                    url,
                )
            )


        return DiscoveredJob(
            job_id=job_id,
            title=title,
            company=(
                company
                or "Unknown"
            ),
            location=location,
            url=url,
            description=str(
                raw_job.get(
                    "snippet",
                    ""
                )
            ),
            source=self.SOURCE_NAME,
            posted_date=str(
                raw_job.get(
                    "updated",
                    ""
                )
            ),
            company_size="Unknown",
            company_size_confidence=(
                "Unknown"
            ),
            published_salary_min=(
                salary_min
            ),
            published_salary_max=(
                salary_max
            ),
            salary_confidence=(
                "High"
                if (
                    salary_min is not None
                    or salary_max is not None
                )
                else "Unknown"
            ),
            metadata={
                "employment_type":
                    raw_job.get(
                        "type"
                    ),
                "original_source":
                    raw_job.get(
                        "source"
                    ),
                "salary_text":
                    salary_text,
            },
        )


    @staticmethod
    def _parse_salary(
        salary_text: str,
    ) -> tuple[
        float | None,
        float | None,
    ]:

        if not salary_text:
            return (
                None,
                None,
            )

        numbers = re.findall(
            r"\d[\d.,]*",
            salary_text,
        )

        parsed = []

        for value in numbers:

            cleaned = (
                value
                .replace(".", "")
                .replace(",", ".")
            )

            try:

                parsed.append(
                    float(cleaned)
                )

            except ValueError:
                continue


        if not parsed:

            return (
                None,
                None,
            )


        if len(parsed) == 1:

            return (
                parsed[0],
                parsed[0],
            )


        return (
            min(parsed[0], parsed[1]),
            max(parsed[0], parsed[1]),
        )


    @staticmethod
    def _create_job_id(
        title: str,
        company: str,
        location: str,
        url: str,
    ) -> str:

        raw = (
            f"{title}|"
            f"{company}|"
            f"{location}|"
            f"{url}"
        ).lower()

        digest = sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        return (
            f"jooble-{digest}"
        )