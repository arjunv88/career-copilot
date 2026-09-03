from dotenv import load_dotenv

from scrapers.sources.jooble import (
    JoobleSource,
)


load_dotenv()


source = JoobleSource(
    max_results=5
)


jobs = source.search_jobs(
    keywords=(
        "Embedded Software Engineer"
    ),
    location="Stuttgart",
)


print(
    "Jobs:",
    len(jobs)
)


for job in jobs:

    print(
        "\n-------------------"
    )

    print(
        job.title
    )

    print(
        job.company
    )

    print(
        job.location
    )

    print(
        job.url
    )