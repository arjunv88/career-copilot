from discovery.geography import (
    analyse_job_location
)


locations = [
    "Taufkirchen",
    "Manching",
    "Stuttgart",
    "Ulm",
    "Karlsruhe",
]


for location in locations:

    result = (
        analyse_job_location(
            location
        )
    )

    print(
        "\n",
        location,
    )

    print(
        result
    )