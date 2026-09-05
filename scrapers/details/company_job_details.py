"""
Career Copilot - detailed company job-page scraper.

Purpose
-------
Discovery sources such as Jooble, Arbeitnow and the Bundesagentur feed can
return only a snippet.  This module follows the selected vacancy toward the
employer/careers page and extracts the most complete job description it can
find.

Design goals
------------
* Prefer structured JobPosting JSON-LD from the employer page.
* Follow HTTP redirects from aggregator links.
* If still on an aggregator page, identify a likely external employer/apply
  link and inspect that page.
* Fall back safely to the discovery-source description when an employer page
  cannot be retrieved.
* Never let a single blocked/changed website crash Career Copilot.
* Use ordinary HTTP requests only; JavaScript-only career sites may require
  manual fallback in the UI.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


@dataclass
class JobDetailResult:
    description: str
    company_url: str
    resolved_url: str
    extraction_method: str
    used_fallback: bool
    warning: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CompanyJobDetailScraper:
    """
    Retrieve a detailed vacancy description, preferably from the employer.

    `fetch_for_job()` accepts the normalized discovered-job dictionary used
    by Career Copilot and returns a JobDetailResult.
    """

    USER_AGENT = (
        "CareerCopilot/0.5 "
        "(portfolio job-analysis assistant; contact via local user)"
    )

    DEFAULT_TIMEOUT_SECONDS = 20
    MIN_USEFUL_DESCRIPTION_CHARS = 300

    # Hosts that should not be treated as the final employer website.
    AGGREGATOR_HOST_FRAGMENTS = (
        "jooble.",
        "arbeitnow.",
        "arbeitsagentur.",
        "stepstone.",
        "indeed.",
        "linkedin.",
        "xing.",
        "glassdoor.",
    )

    # External links to avoid when looking for an employer/careers page.
    EXCLUDED_HOST_FRAGMENTS = (
        "facebook.",
        "instagram.",
        "youtube.",
        "twitter.",
        "x.com",
        "tiktok.",
        "whatsapp.",
        "google.",
        "doubleclick.",
    )

    APPLY_HINTS = (
        "apply",
        "bewerben",
        "bewerbung",
        "karriere",
        "career",
        "careers",
        "jobs",
        "job",
        "stellenangebot",
        "vacancy",
        "position",
    )

    DESCRIPTION_SELECTORS = (
        "[itemprop='description']",
        "[data-testid*='description']",
        "[class*='job-description']",
        "[class*='job_description']",
        "[class*='jobDescription']",
        "[id*='job-description']",
        "[id*='job_description']",
        "[id*='jobDescription']",
        "article",
        "main",
    )

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        respect_robots_txt: bool = True,
    ):
        self.timeout_seconds = int(timeout_seconds)
        self.respect_robots_txt = bool(respect_robots_txt)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            }
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_for_job(
        self,
        job: dict,
    ) -> JobDetailResult:
        if not isinstance(job, dict):
            raise TypeError("job must be a dictionary.")

        original_url = str(
            job.get("url", "") or ""
        ).strip()

        fallback_description = self._clean_text(
            str(job.get("description", "") or "")
        )

        title = str(
            job.get("title", "") or ""
        ).strip()

        company = str(
            job.get("company", "") or ""
        ).strip()

        if not original_url:
            return self._fallback_result(
                fallback_description,
                warning=(
                    "The discovery source did not provide a job URL. "
                    "Using the available source description."
                ),
            )

        try:
            first_page = self._fetch_page(
                original_url
            )
        except Exception as error:
            return self._fallback_result(
                fallback_description,
                resolved_url=original_url,
                warning=(
                    "The source job page could not be opened: "
                    f"{error}"
                ),
            )

        first_url = first_page.url
        first_soup = BeautifulSoup(
            first_page.text,
            "html.parser",
        )

        # If HTTP redirects already landed on a non-aggregator employer
        # domain, extract directly from that page.
        if not self._is_aggregator_url(
            first_url
        ):
            result = self._extract_from_page(
                first_soup,
                page_url=first_url,
                company_url=first_url,
                title=title,
                company=company,
            )

            if result is not None:
                return result

        # We are still on an aggregator/source page. Search for the most
        # plausible outbound employer/apply URL.
        external_url = self._find_best_external_job_url(
            soup=first_soup,
            page_url=first_url,
            company=company,
        )

        if external_url:
            try:
                employer_page = self._fetch_page(
                    external_url
                )

                employer_url = employer_page.url
                employer_soup = BeautifulSoup(
                    employer_page.text,
                    "html.parser",
                )

                result = self._extract_from_page(
                    employer_soup,
                    page_url=employer_url,
                    company_url=employer_url,
                    title=title,
                    company=company,
                )

                if result is not None:
                    return result

            except Exception as error:
                employer_error = str(error)
            else:
                employer_error = ""
        else:
            employer_error = (
                "No external employer/careers link was found "
                "on the source page."
            )

        # As a secondary fallback, a source page may itself contain a full
        # JobPosting description. Use it, but label it honestly.
        source_result = self._extract_from_page(
            first_soup,
            page_url=first_url,
            company_url="",
            title=title,
            company=company,
            force_fallback=True,
        )

        if source_result is not None:
            source_result.warning = (
                "A full employer page could not be retrieved. "
                "Using the most complete description available on the "
                f"discovery source. {employer_error}"
            ).strip()
            return source_result

        return self._fallback_result(
            fallback_description,
            resolved_url=first_url,
            warning=(
                "A detailed employer description could not be retrieved. "
                f"{employer_error} "
                "You can still open the original vacancy and paste the "
                "complete description manually."
            ).strip(),
        )

    # ------------------------------------------------------------------
    # HTTP / robots
    # ------------------------------------------------------------------

    def _fetch_page(
        self,
        url: str,
    ) -> requests.Response:
        url = self._validate_http_url(
            url
        )

        if (
            self.respect_robots_txt
            and not self._robots_allows(url)
        ):
            raise PermissionError(
                "robots.txt does not allow automated retrieval "
                "of this page."
            )

        response = self.session.get(
            url,
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )

        response.raise_for_status()

        content_type = str(
            response.headers.get(
                "Content-Type",
                "",
            )
        ).lower()

        if (
            "text/html" not in content_type
            and "application/xhtml" not in content_type
            and content_type
        ):
            raise ValueError(
                f"Unsupported page content type: {content_type}"
            )

        # Avoid huge downloads being processed as job pages.
        if len(response.content) > 8_000_000:
            raise ValueError(
                "The retrieved page is unexpectedly large."
            )

        return response

    def _robots_allows(
        self,
        url: str,
    ) -> bool:
        """
        Honor explicit robots exclusions.

        If robots.txt itself is unavailable, fail open because a transient
        robots request failure should not make the portfolio app unusable.
        """

        parsed = urlparse(url)

        robots_url = (
            f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        )

        parser = RobotFileParser()

        try:
            parser.set_url(
                robots_url
            )
            parser.read()

            return parser.can_fetch(
                self.USER_AGENT,
                url,
            )
        except Exception:
            return True

    @staticmethod
    def _validate_http_url(
        url: str,
    ) -> str:
        parsed = urlparse(
            str(url).strip()
        )

        if parsed.scheme not in (
            "http",
            "https",
        ):
            raise ValueError(
                "Only HTTP/HTTPS job URLs are supported."
            )

        if not parsed.netloc:
            raise ValueError(
                "The job URL has no valid host."
            )

        return parsed.geturl()

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_from_page(
        self,
        soup: BeautifulSoup,
        page_url: str,
        company_url: str,
        title: str,
        company: str,
        force_fallback: bool = False,
    ) -> JobDetailResult | None:
        structured = self._extract_jobposting_jsonld(
            soup
        )

        if structured:
            description = self._clean_html_fragment(
                structured.get(
                    "description",
                    "",
                )
            )

            if self._description_is_useful(
                description,
                title=title,
                company=company,
            ):
                structured_url = str(
                    structured.get("url", "") or ""
                ).strip()

                final_company_url = (
                    urljoin(
                        page_url,
                        structured_url,
                    )
                    if structured_url
                    else company_url
                )

                return JobDetailResult(
                    description=description,
                    company_url=(
                        final_company_url
                        if not force_fallback
                        else ""
                    ),
                    resolved_url=page_url,
                    extraction_method=(
                        "json-ld JobPosting"
                    ),
                    used_fallback=force_fallback,
                )

        # Try common semantic containers before falling back to whole-page
        # content.
        for selector in self.DESCRIPTION_SELECTORS:
            element = soup.select_one(
                selector
            )

            if element is None:
                continue

            description = self._clean_text(
                element.get_text(
                    "\n",
                    strip=True,
                )
            )

            if self._description_is_useful(
                description,
                title=title,
                company=company,
            ):
                return JobDetailResult(
                    description=description,
                    company_url=(
                        company_url
                        if not force_fallback
                        else ""
                    ),
                    resolved_url=page_url,
                    extraction_method=(
                        f"html selector: {selector}"
                    ),
                    used_fallback=force_fallback,
                )

        return None

    def _extract_jobposting_jsonld(
        self,
        soup: BeautifulSoup,
    ) -> dict | None:
        for script in soup.find_all(
            "script",
            attrs={"type": "application/ld+json"},
        ):
            raw = script.string or script.get_text()

            if not raw or not raw.strip():
                continue

            try:
                data = json.loads(
                    raw
                )
            except (json.JSONDecodeError, TypeError):
                continue

            for node in self._walk_jsonld(
                data
            ):
                node_type = node.get(
                    "@type"
                )

                if isinstance(
                    node_type,
                    list,
                ):
                    node_types = {
                        str(item).lower()
                        for item in node_type
                    }
                else:
                    node_types = {
                        str(node_type).lower()
                    }

                if "jobposting" in node_types:
                    return node

        return None

    def _walk_jsonld(
        self,
        value: Any,
    ):
        if isinstance(value, dict):
            yield value

            graph = value.get(
                "@graph"
            )

            if isinstance(
                graph,
                list,
            ):
                for item in graph:
                    yield from self._walk_jsonld(
                        item
                    )

        elif isinstance(
            value,
            list,
        ):
            for item in value:
                yield from self._walk_jsonld(
                    item
                )

    # ------------------------------------------------------------------
    # External employer-link discovery
    # ------------------------------------------------------------------

    def _find_best_external_job_url(
        self,
        soup: BeautifulSoup,
        page_url: str,
        company: str,
    ) -> str:
        page_host = self._host(
            page_url
        )

        company_tokens = {
            token
            for token in self._normalize_words(
                company
            )
            if len(token) >= 3
        }

        candidates: list[
            tuple[int, str]
        ] = []

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = str(
                anchor.get("href", "")
            ).strip()

            if not href:
                continue

            absolute_url = urljoin(
                page_url,
                href,
            )

            try:
                absolute_url = self._validate_http_url(
                    absolute_url
                )
            except ValueError:
                continue

            host = self._host(
                absolute_url
            )

            if not host:
                continue

            if host == page_host:
                continue

            if any(
                fragment in host
                for fragment in self.EXCLUDED_HOST_FRAGMENTS
            ):
                continue

            anchor_text = self._clean_text(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            ).lower()

            url_lower = (
                absolute_url.lower()
            )

            score = 0

            if not self._is_aggregator_url(
                absolute_url
            ):
                score += 20

            for hint in self.APPLY_HINTS:
                if hint in anchor_text:
                    score += 12

                if hint in url_lower:
                    score += 6

            if company_tokens:
                normalized_target = set(
                    self._normalize_words(
                        host
                        + " "
                        + anchor_text
                    )
                )

                score += (
                    len(
                        company_tokens
                        & normalized_target
                    )
                    * 8
                )

            # Buttons/CTAs are often the desired external apply link.
            css_classes = " ".join(
                anchor.get(
                    "class",
                    [],
                )
            ).lower()

            if (
                "button" in css_classes
                or "apply" in css_classes
                or "bewerb" in css_classes
            ):
                score += 8

            candidates.append(
                (
                    score,
                    absolute_url,
                )
            )

        if not candidates:
            return ""

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        best_score, best_url = (
            candidates[0]
        )

        # Require evidence beyond merely being external. This avoids
        # following arbitrary privacy/support/vendor links.
        if best_score < 26:
            return ""

        return best_url

    # ------------------------------------------------------------------
    # Validation / cleaning helpers
    # ------------------------------------------------------------------

    def _description_is_useful(
        self,
        description: str,
        title: str,
        company: str,
    ) -> bool:
        if len(description) < self.MIN_USEFUL_DESCRIPTION_CHARS:
            return False

        normalized = (
            description.lower()
        )

        # Reject obvious generic error/cookie pages.
        error_markers = (
            "page not found",
            "404 not found",
            "access denied",
            "enable javascript to continue",
        )

        if any(
            marker in normalized
            for marker in error_markers
        ):
            return False

        # Relevance is intentionally permissive. Not every employer repeats
        # the exact title/company in the description body.
        title_tokens = {
            token
            for token in self._normalize_words(
                title
            )
            if len(token) >= 4
        }

        if not title_tokens:
            return True

        description_tokens = set(
            self._normalize_words(
                description
            )
        )

        return bool(
            title_tokens
            & description_tokens
        )

    @staticmethod
    def _clean_html_fragment(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        soup = BeautifulSoup(
            unescape(
                str(value)
            ),
            "html.parser",
        )

        return CompanyJobDetailScraper._clean_text(
            soup.get_text(
                "\n",
                strip=True,
            )
        )

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        text = unescape(
            str(value)
        )

        text = text.replace(
            "\xa0",
            " ",
        )

        # Preserve paragraph-ish line breaks while collapsing noise.
        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n[ \t]+",
            "\n",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    @staticmethod
    def _normalize_words(
        value: Any,
    ) -> list[str]:
        return re.findall(
            r"[a-z0-9+#]+",
            str(value or "").lower(),
        )

    @classmethod
    def _is_aggregator_url(
        cls,
        url: str,
    ) -> bool:
        host = cls._host(
            url
        )

        return any(
            fragment in host
            for fragment in cls.AGGREGATOR_HOST_FRAGMENTS
        )

    @staticmethod
    def _host(
        url: str,
    ) -> str:
        host = (
            urlparse(
                str(url)
            )
            .netloc
            .lower()
            .split("@")[-1]
            .split(":")[0]
        )

        if host.startswith(
            "www."
        ):
            host = host[4:]

        return host

    @staticmethod
    def _fallback_result(
        description: str,
        resolved_url: str = "",
        warning: str = "",
    ) -> JobDetailResult:
        return JobDetailResult(
            description=description,
            company_url="",
            resolved_url=resolved_url,
            extraction_method=(
                "discovery-source fallback"
            ),
            used_fallback=True,
            warning=warning,
        )
