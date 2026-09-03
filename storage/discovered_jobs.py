import json
from pathlib import Path


DISCOVERED_JOBS_FILE = Path(
    "data/discovered_jobs.json"
)


def save_discovered_jobs(
    jobs: list[dict],
):

    DISCOVERED_JOBS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DISCOVERED_JOBS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            jobs,
            file,
            indent=2,
            ensure_ascii=False,
        )


def load_discovered_jobs():

    if not (
        DISCOVERED_JOBS_FILE.exists()
    ):
        return []

    try:

        with DISCOVERED_JOBS_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception:

        return []