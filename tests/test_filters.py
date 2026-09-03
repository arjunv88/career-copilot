from discovery.filters import (
    company_size_allowed,
    company_size_score,
)

from discovery.salary import (
    salary_score,
    salary_is_promising,
)


print(
    "Large:",
    company_size_allowed("Large"),
    company_size_score("Large"),
)

print(
    "Small:",
    company_size_allowed("Small"),
    company_size_score("Small"),
)

print(
    "Unknown:",
    company_size_allowed("Unknown"),
    company_size_score("Unknown"),
)


print(
    "Salary 90k:",
    salary_score(
        90000,
        100000,
        None,
        None,
    ),
)

print(
    "Salary 65k:",
    salary_score(
        60000,
        65000,
        None,
        None,
    ),
)

print(
    "Unknown salary:",
    salary_score(
        None,
        None,
        None,
        None,
    ),
)