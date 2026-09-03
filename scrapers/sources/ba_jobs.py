import base64
from hashlib import sha256

import requests

from scrapers.base import JobSource
from scrapers.models import DiscoveredJob


class BAJobsSource(JobSource):

    SOURCE_NAME = (
        "Bundesagentur für Arbeit"
    )

    SEARCH_URL = (
        "https://rest.arbeitsagentur.de/"
        "jobboerse/jobsuche-service/"
        "pc/v6/jobs"
    )

    DETAILS_URL = (
        "https://rest.arbeitsagentur.de/"
        "jobboerse/jobsuche-service/"
        "pc/v4/jobdetails"
    )


    HEADERS = {
        "X-API-Key":
            "jobboerse-jobsuche"
    }


    def __init__(
        self,
        max_results: int = 10,
        load_details: bool = True,
    ):

        self.max_results = max_results

        self.load_details = (
            load_details
        )


    def search_jobs(
        self,
        keywords: str,
        location: str,
    ) -> list[DiscoveredJob]:

        params = {
            "was": keywords,
            "wo": location,

            # BA supports a direct
            # 50 km search radius.
            "umkreis": 50,

            # 1 = regular job offers
            "angebotsart": 1,

            # Full-time
            "arbeitszeit": "vz",

            "page": 1,
            "size": self.max_results,
        }


        response = requests.get(
            self.SEARCH_URL,
            headers=self.HEADERS,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()


        raw_jobs = (
            data.get("stellenangebote")
            or data.get("jobs")
            or data.get("items")
            or []
        )


        discovered_jobs = []


        for raw_job in raw_jobs[
            :self.max_results
        ]:

            try:

                job = self._convert_job(
                    raw_job
                )

                if job is not None:

                    discovered_jobs.append(
                        job
                    )

            except Exception as error:

                print(
                    "Skipping BA job because "
                    "conversion failed:",
                    error,
                )


        return discovered_jobs


    def _convert_job(
        self,
        raw_job: dict,
    ) -> DiscoveredJob | None:

        reference = self._first(
            raw_job,
            "referenznummer",
            "refnr",
        )


        title = self._first(
            raw_job,
            "titel",
            "stellenangebotsTitel",
            "beruf",
        )


        company = self._first(
            raw_job,
            "arbeitgeber",
            "arbeitgebername",
            "firma",
        )


        location = self._extract_location(
            raw_job
        )


        external_url = self._first(
            raw_job,
            "externeUrl",
            "externeURL",
            "url",
        )


        posted_date = self._first(
            raw_job,
            "aktuelleVeroeffentlichungsdatum",
            "veroeffentlichungsdatum",
            "eintrittsdatum",
        )


        description = ""


        if (
            reference
            and self.load_details
        ):

            details = (
                self._load_details(
                    reference
                )
            )

            if details:

                description = str(
                    self._first(
                        details,
                        "stellenangebotsBeschreibung",
                        "beschreibung",
                    )
                    or ""
                )


                detail_title = (
                    self._first(
                        details,
                        "stellenangebotsTitel",
                        "titel",
                    )
                )

                if detail_title:

                    title = detail_title


                detail_company = (
                    self._first(
                        details,
                        "arbeitgeber",
                        "arbeitgebername",
                    )
                )

                if detail_company:

                    company = (
                        detail_company
                    )


        if not title:
            return None

        if not location:
            return None


        if external_url:

            job_url = str(
                external_url
            )

        elif reference:

            # There is not always an
            # external employer URL.
            # We keep a BA search URL
            # as a usable fallback.
            job_url = (
                "https://www.arbeitsagentur.de/"
                "jobsuche/jobdetail/"
                f"{reference}"
            )

        else:

            job_url = (
                "https://www.arbeitsagentur.de/"
                "jobsuche/"
            )


        if reference:

            job_id = (
                f"ba-{reference}"
            )

        else:

            job_id = (
                self._create_job_id(
                    str(title),
                    str(company),
                    str(location),
                )
            )


        return DiscoveredJob(
            job_id=str(job_id),
            title=str(title),
            company=(
                str(company)
                if company
                else "Unknown"
            ),
            location=str(location),
            url=str(job_url),
            description=description,
            source=self.SOURCE_NAME,
            posted_date=(
                str(posted_date)
                if posted_date
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
                "reference_number":
                    reference,
                "experimental_source":
                    True,
            },
        )


    def _load_details(
        self,
        reference: str,
    ) -> dict | None:

        encoded_reference = (
            base64.b64encode(
                reference.encode(
                    "utf-8"
                )
            )
            .decode(
                "utf-8"
            )
        )


        url = (
            f"{self.DETAILS_URL}/"
            f"{encoded_reference}"
        )


        try:

            response = requests.get(
                url,
                headers=self.HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException:
            return None


    @staticmethod
    def _extract_location(
        raw_job: dict,
    ) -> str:

        arbeitsort = raw_job.get(
            "arbeitsort"
        )


        if isinstance(
            arbeitsort,
            dict,
        ):

            city = (
                arbeitsort.get("ort")
                or arbeitsort.get(
                    "stadt"
                )
                or ""
            )

            postcode = (
                arbeitsort.get(
                    "plz"
                )
                or ""
            )

            if city and postcode:

                return (
                    f"{postcode} {city}"
                )

            if city:

                return str(city)


        if isinstance(
            arbeitsort,
            str,
        ):

            return arbeitsort


        locations = raw_job.get(
            "arbeitsorte"
        )


        if (
            isinstance(
                locations,
                list,
            )
            and locations
        ):

            first_location = (
                locations[0]
            )

            if isinstance(
                first_location,
                dict,
            ):

                city = (
                    first_location.get(
                        "ort"
                    )
                    or first_location.get(
                        "stadt"
                    )
                    or ""
                )

                postcode = (
                    first_location.get(
                        "plz"
                    )
                    or ""
                )

                if city and postcode:

                    return (
                        f"{postcode} {city}"
                    )

                if city:

                    return str(city)


        return ""


    @staticmethod
    def _first(
        data: dict,
        *keys,
    ):

        for key in keys:

            value = data.get(
                key
            )

            if value not in (
                None,
                "",
            ):

                return value

        return None


    @staticmethod
    def _create_job_id(
        title: str,
        company: str,
        location: str,
    ) -> str:

        raw = (
            f"{title}|"
            f"{company}|"
            f"{location}"
        ).lower()

        digest = sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        return (
            f"ba-{digest}"
        )