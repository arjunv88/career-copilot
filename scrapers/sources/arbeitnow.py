import re
from html import unescape

import requests

from scrapers.base import JobSource
from scrapers.models import DiscoveredJob


class ArbeitnowSource(JobSource):

    SOURCE_NAME = "Arbeitnow"

    BASE_URL = (
        "https://www.arbeitnow.com/"
        "api/job-board-api"
    )


    def __init__(
        self,
        max_pages: int = 3,
    ):

        self.max_pages = max_pages


    def search_jobs(
        self,
        keywords: str,
        location: str,
    ) -> list[DiscoveredJob]:

        discovered_jobs = []

        keyword_tokens = (
            self._keyword_tokens(
                keywords
            )
        )


        for page in range(
            1,
            self.max_pages + 1,
        ):

            response = requests.get(
                self.BASE_URL,
                params={
                    "page": page,
                },
                timeout=30,
            )

            response.raise_for_status()

            data = response.json()

            raw_jobs = data.get(
                "data",
                []
            )


            for raw_job in raw_jobs:

                if not (
                    self._matches_keywords(
                        raw_job,
                        keyword_tokens,
                    )
                ):

                    continue


                job = self._convert_job(
                    raw_job
                )

                if job is not None:

                    discovered_jobs.append(
                        job
                    )


            links = data.get(
                "links",
                {}
            )

            if not links.get(
                "next"
            ):

                break


        return discovered_jobs


    def _matches_keywords(
        self,
        raw_job: dict,
        keyword_tokens: list[str],
    ) -> bool:

        if not keyword_tokens:

            return True


        title = str(
            raw_job.get(
                "title",
                ""
            )
        )

        description = str(
            raw_job.get(
                "description",
                ""
            )
        )

        tags = raw_job.get(
            "tags",
            []
        )

        if not isinstance(
            tags,
            list,
        ):

            tags = []


        searchable_text = (
            f"{title} "
            f"{description} "
            f"{' '.join(str(tag) for tag in tags)}"
        ).lower()


        matches = sum(
            1
            for token
            in keyword_tokens
            if token in searchable_text
        )


        # At least one meaningful
        # keyword should match.
        return (
            matches >= 1
        )


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
                "company_name",
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
                "url",
                ""
            )
        ).strip()

        slug = str(
            raw_job.get(
                "slug",
                ""
            )
        ).strip()


        if not title:
            return None

        if not location:
            return None

        if not url:
            return None


        description = (
            self._clean_html(
                str(
                    raw_job.get(
                        "description",
                        ""
                    )
                )
            )
        )


        if slug:

            job_id = (
                f"arbeitnow-{slug}"
            )

        else:

            job_id = (
                f"arbeitnow-"
                f"{abs(hash(url))}"
            )


        created_at = raw_job.get(
            "created_at"
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
            description=description,
            source=self.SOURCE_NAME,
            posted_date=(
                str(created_at)
                if created_at
                else ""
            ),
            company_size="Unknown",
            company_size_confidence=(
                "Unknown"
            ),
            published_salary_min=None,
            published_salary_max=None,
            salary_confidence="Unknown",
            metadata={
                "remote":
                    raw_job.get(
                        "remote",
                        False
                    ),
                "tags":
                    raw_job.get(
                        "tags",
                        []
                    ),
                "job_types":
                    raw_job.get(
                        "job_types",
                        []
                    ),
            },
        )


    @staticmethod
    def _keyword_tokens(
        keywords: str,
    ) -> list[str]:

        words = re.findall(
            r"[a-zA-Z0-9+#]+",
            keywords.lower(),
        )

        ignored = {
            "senior",
            "junior",
            "engineer",
            "developer",
            "software",
        }

        meaningful = [
            word
            for word in words
            if (
                len(word) >= 2
                and word
                not in ignored
            )
        ]


        if meaningful:

            return meaningful


        return words


    @staticmethod
    def _clean_html(
        text: str,
    ) -> str:

        text = re.sub(
            r"<br\s*/?>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            text,
        )

        text = unescape(
            text
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n\s*\n+",
            "\n",
            text,
        )

        return text.strip()