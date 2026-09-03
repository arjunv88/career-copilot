MIN_TARGET_SALARY = 80000


def salary_score(
    published_salary_min: float | None,
    published_salary_max: float | None,
    estimated_salary_min: float | None,
    estimated_salary_max: float | None,
    minimum_salary: float = MIN_TARGET_SALARY,
) -> float:

    if published_salary_min is not None:

        if (
            published_salary_min
            >= minimum_salary
        ):
            return 100.0


    if published_salary_max is not None:

        if (
            published_salary_max
            >= minimum_salary
        ):
            return 100.0

        return 20.0


    if estimated_salary_min is not None:

        if (
            estimated_salary_min
            >= minimum_salary
        ):
            return 80.0


    if estimated_salary_max is not None:

        if (
            estimated_salary_max
            >= minimum_salary
        ):
            return 80.0

        return 30.0


    # Salary unknown.
    # Do not reject automatically.
    return 50.0


def salary_is_promising(
    published_salary_min: float | None,
    published_salary_max: float | None,
    estimated_salary_min: float | None,
    estimated_salary_max: float | None,
    minimum_salary: float = MIN_TARGET_SALARY,
) -> bool:

    score = salary_score(
        published_salary_min,
        published_salary_max,
        estimated_salary_min,
        estimated_salary_max,
        minimum_salary,
    )

    return (
        score >= 50.0
    )