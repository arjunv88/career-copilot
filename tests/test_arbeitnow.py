from scrapers.sources.arbeitnow import (
    ArbeitnowSource,
)


source = ArbeitnowSource(
    max_pages=2
)


jobs = source.search_jobs(
    keywords="C++ Developer",
    location="Germany",
)


print(
    "Jobs:",
    len(jobs)
)


for job in jobs[:10]:

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