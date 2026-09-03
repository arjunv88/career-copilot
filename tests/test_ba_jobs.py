from scrapers.sources.ba_jobs import (
    BAJobsSource,
)


source = BAJobsSource(
    max_results=5,
    load_details=True,
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

    print(
        "Description length:",
        len(
            job.description
        ),
    )