#include <algorithm>
#include <cctype>
#include <string>
#include <unordered_set>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;


std::string normalize_skill(
    std::string skill
)
{
    std::transform(
        skill.begin(),
        skill.end(),
        skill.begin(),
        [](unsigned char c)
        {
            return std::tolower(c);
        }
    );

    // Remove spaces
    skill.erase(
        std::remove(
            skill.begin(),
            skill.end(),
            ' '
        ),
        skill.end()
    );

    // Common aliases
    if (
        skill == "embeddedc/c++"
        ||
        skill == "cpp"
        ||
        skill == "modernc++"
    )
    {
        return "c++";
    }

    if (
        skill == "matlab/simulink"
        ||
        skill == "matlab/simulink"
        ||
        skill == "matlab"
        ||
        skill == "simulink"
    )
    {
        return "matlab_simulink";
    }

    if (
        skill == "iso26262(asil-d)"
        ||
        skill == "iso26262"
    )
    {
        return "iso26262";
    }

    if (
        skill == "realtimesystems"
        ||
        skill == "real-timesystems"
        ||
        skill == "realtimesoftware"
    )
    {
        return "real_time_systems";
    }

    return skill;
}

struct MatchResult
{
    double score;

    std::vector<std::string>
        matched_skills;

    std::vector<std::string>
        missing_skills;
};


MatchResult calculate_match(
    const std::vector<std::string>&
        candidate_skills,

    const std::vector<std::string>&
        required_skills
)
{
    std::unordered_set<
        std::string
    > candidate_set;

    for (
        const auto& skill :
        candidate_skills
    )
    {
        candidate_set.insert(
            normalize_skill(skill)
        );
    }


    MatchResult result;

    result.score = 0.0;


    for (
        const auto& skill :
        required_skills
    )
    {
        std::string normalized =
            normalize_skill(skill);


        if (
            candidate_set.contains(
                normalized
            )
        )
        {
            result.matched_skills
                .push_back(skill);
        }

        else
        {
            result.missing_skills
                .push_back(skill);
        }
    }


    if (!required_skills.empty())
    {
        result.score =
            (
                static_cast<double>(
                    result
                    .matched_skills
                    .size()
                )
                /
                required_skills.size()
            )
            * 100.0;
    }


    return result;
}


PYBIND11_MODULE(
    match_engine,
    module
)
{
    py::class_<
        MatchResult
    >(
        module,
        "MatchResult"
    )

    .def_readonly(
        "score",
        &MatchResult::score
    )

    .def_readonly(
        "matched_skills",
        &MatchResult::
            matched_skills
    )

    .def_readonly(
        "missing_skills",
        &MatchResult::
            missing_skills
    );


    module.def(
        "calculate_match",
        &calculate_match,
        "Calculate job compatibility"
    );
}