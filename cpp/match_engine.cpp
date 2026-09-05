#include <algorithm>
#include <cmath>
#include <cctype>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

struct SkillMatchDetail {
    std::string job_skill;
    std::string candidate_skill;
    std::string match_type;
    double strength = 0.0;
    double requirement_weight = 1.0;
};

struct MatchResult {
    double score = 0.0;
    std::vector<std::string> matched_skills;
    std::vector<std::string> related_skills;
    std::vector<std::string> preferred_matches;
    std::vector<std::string> missing_skills;
    std::vector<SkillMatchDetail> details;
};

static std::string trim(const std::string& input) {
    const auto first = input.find_first_not_of(" \t\n\r");
    if (first == std::string::npos) return "";
    const auto last = input.find_last_not_of(" \t\n\r");
    return input.substr(first, last - first + 1);
}

static std::string normalize_basic(std::string text) {
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });

    for (char& c : text) {
        if (c == '_' || c == '/' || c == '\\' || c == '-' || c == '&' || c == '(' || c == ')' || c == ',' || c == ';' || c == ':') {
            c = ' ';
        }
    }

    std::string out;
    bool previous_space = false;
    for (unsigned char c : text) {
        const bool keep = std::isalnum(c) || c == '+' || c == '#' || c == '.';
        if (keep) {
            out.push_back(static_cast<char>(c));
            previous_space = false;
        } else if (!previous_space) {
            out.push_back(' ');
            previous_space = true;
        }
    }
    return trim(out);
}

static const std::unordered_map<std::string, std::string>& alias_map() {
    static const std::unordered_map<std::string, std::string> aliases = {
        {"cpp", "c++"}, {"modern c++", "c++"}, {"c++17", "c++"}, {"c++20", "c++"},
        {"embedded c++", "c++"}, {"embedded c c++", "c++"},
        {"iso26262", "iso 26262"}, {"iso 26262 asil d", "iso 26262"}, {"functional safety", "iso 26262"},
        {"asil d", "asil-d"}, {"asild", "asil-d"},
        {"matlab simulink", "matlab/simulink"}, {"matlab", "matlab/simulink"}, {"simulink", "matlab/simulink"},
        {"hardware in the loop", "hil"}, {"hardware in loop", "hil"},
        {"software in the loop", "sil"}, {"software in loop", "sil"},
        {"driver in the loop", "dil"}, {"driver in loop", "dil"},
        {"continuous integration", "ci/cd"}, {"continuous delivery", "ci/cd"}, {"continuous deployment", "ci/cd"},
        {"ibm doors", "doors"}, {"requirements management doors", "doors"},
        {"classic autosar", "autosar"}, {"autosar classic", "autosar"},
        {"real time systems", "real-time systems"}, {"real time software", "real-time systems"},
        {"object oriented programming", "oop"},
        {"model based systems engineering", "mbse"},
        {"verification validation", "verification & validation"},
    };
    return aliases;
}

static std::string canonicalize(const std::string& raw) {
    const std::string normalized = normalize_basic(raw);
    const auto it = alias_map().find(normalized);
    return it != alias_map().end() ? it->second : normalized;
}

static std::set<std::string> token_set(const std::string& text) {
    std::set<std::string> tokens;
    std::istringstream stream(normalize_basic(text));
    std::string token;
    while (stream >> token) {
        if (token.size() >= 2) tokens.insert(token);
    }
    return tokens;
}

static double token_similarity(const std::string& a, const std::string& b) {
    const auto aa = token_set(a);
    const auto bb = token_set(b);
    if (aa.empty() || bb.empty()) return 0.0;
    std::size_t intersection = 0;
    for (const auto& token : aa) {
        if (bb.contains(token)) ++intersection;
    }
    const std::size_t union_size = aa.size() + bb.size() - intersection;
    if (union_size == 0) return 0.0;
    return static_cast<double>(intersection) / static_cast<double>(union_size);
}

static double related_strength(const std::string& a, const std::string& b) {
    const std::string ca = canonicalize(a);
    const std::string cb = canonicalize(b);
    if (ca == cb) return 1.0;

    static const std::vector<std::pair<std::unordered_set<std::string>, double>> families = {
        {{"embedded systems", "embedded software", "firmware", "real-time systems"}, 0.72},
        {{"system integration", "software integration", "hardware software integration"}, 0.72},
        {{"verification & validation", "testing", "system validation", "software testing"}, 0.68},
        {{"hil", "sil", "dil", "pil", "virtual validation"}, 0.62},
        {{"system architecture", "software architecture", "technical architecture", "mbse", "uml"}, 0.66},
        {{"can", "canoe", "canape", "automotive ethernet", "ethernet"}, 0.58},
        {{"cmake", "build systems", "conan"}, 0.58},
        {{"jenkins", "ci/cd", "artifactory", "conan"}, 0.62},
        {{"control engineering", "control systems", "controller development"}, 0.70},
        {{"simulation", "real-time simulation", "dspace", "carmaker", "rapid prototyping"}, 0.68},
        {{"iso 26262", "asil-d", "safety-critical design", "functional safety"}, 0.74},
    };

    for (const auto& [family, strength] : families) {
        if (family.contains(ca) && family.contains(cb)) return strength;
    }

    const double token = token_similarity(ca, cb);
    // Conservative fuzzy relation: only multi-token phrases with meaningful overlap.
    if (token >= 0.66 && token_set(ca).size() >= 2 && token_set(cb).size() >= 2) {
        return 0.55 + (token - 0.66) * 0.35;
    }
    return 0.0;
}

struct BestMatch {
    std::string candidate_skill;
    double strength = 0.0;
    std::string type = "none";
};

static BestMatch find_best_match(
    const std::string& job_skill,
    const std::vector<std::string>& candidate_skills,
    const std::unordered_map<std::string, double>& candidate_weights
) {
    BestMatch best;
    const std::string job_canonical = canonicalize(job_skill);

    for (const auto& candidate : candidate_skills) {
        const std::string cand_canonical = canonicalize(candidate);
        double base = related_strength(job_skill, candidate);
        if (base <= 0.0) continue;

        double evidence_weight = 1.0;
        const auto direct = candidate_weights.find(candidate);
        const auto canonical = candidate_weights.find(cand_canonical);
        if (direct != candidate_weights.end()) evidence_weight = direct->second;
        else if (canonical != candidate_weights.end()) evidence_weight = canonical->second;

        evidence_weight = std::clamp(evidence_weight, 0.5, 1.0);
        const double weighted = base * evidence_weight;
        if (weighted > best.strength) {
            best.candidate_skill = candidate;
            best.strength = weighted;
            if (job_canonical == cand_canonical) {
                best.type = normalize_basic(job_skill) == normalize_basic(candidate) ? "exact" : "alias";
            } else {
                best.type = "related";
            }
        }
    }
    return best;
}

static void score_requirements(
    const std::vector<std::string>& requirements,
    double requirement_weight,
    bool preferred,
    const std::vector<std::string>& candidate_skills,
    const std::unordered_map<std::string, double>& candidate_weights,
    MatchResult& result,
    double& earned,
    double& possible
) {
    for (const auto& skill : requirements) {
        if (trim(skill).empty()) continue;
        possible += requirement_weight;
        const BestMatch best = find_best_match(skill, candidate_skills, candidate_weights);
        earned += best.strength * requirement_weight;

        SkillMatchDetail detail;
        detail.job_skill = skill;
        detail.candidate_skill = best.candidate_skill;
        detail.match_type = best.type;
        detail.strength = best.strength;
        detail.requirement_weight = requirement_weight;
        result.details.push_back(detail);

        if (best.strength >= 0.85) {
            if (preferred) result.preferred_matches.push_back(skill);
            else result.matched_skills.push_back(skill);
        } else if (best.strength >= 0.50) {
            std::ostringstream text;
            text << skill << " <- " << best.candidate_skill << " (" << best.type << ", "
                 << static_cast<int>(std::round(best.strength * 100.0)) << "%)";
            result.related_skills.push_back(text.str());
        } else if (!preferred) {
            result.missing_skills.push_back(skill);
        }
    }
}

MatchResult calculate_match(
    const std::vector<std::string>& candidate_skills,
    const std::vector<std::string>& required_skills,
    const std::vector<std::string>& preferred_skills = {},
    const std::unordered_map<std::string, double>& candidate_weights = {}
) {
    MatchResult result;
    double earned = 0.0;
    double possible = 0.0;

    // Required skills dominate; preferred requirements add signal without
    // allowing optional items to overwhelm genuine mandatory gaps.
    score_requirements(required_skills, 1.0, false, candidate_skills, candidate_weights, result, earned, possible);
    score_requirements(preferred_skills, 0.45, true, candidate_skills, candidate_weights, result, earned, possible);

    if (possible > 0.0) {
        result.score = std::clamp((earned / possible) * 100.0, 0.0, 100.0);
    }
    return result;
}

PYBIND11_MODULE(match_engine, module) {
    py::class_<SkillMatchDetail>(module, "SkillMatchDetail")
        .def_readonly("job_skill", &SkillMatchDetail::job_skill)
        .def_readonly("candidate_skill", &SkillMatchDetail::candidate_skill)
        .def_readonly("match_type", &SkillMatchDetail::match_type)
        .def_readonly("strength", &SkillMatchDetail::strength)
        .def_readonly("requirement_weight", &SkillMatchDetail::requirement_weight);

    py::class_<MatchResult>(module, "MatchResult")
        .def_readonly("score", &MatchResult::score)
        .def_readonly("matched_skills", &MatchResult::matched_skills)
        .def_readonly("related_skills", &MatchResult::related_skills)
        .def_readonly("preferred_matches", &MatchResult::preferred_matches)
        .def_readonly("missing_skills", &MatchResult::missing_skills)
        .def_readonly("details", &MatchResult::details);

    module.def(
        "calculate_match",
        &calculate_match,
        py::arg("candidate_skills"),
        py::arg("required_skills"),
        py::arg("preferred_skills") = std::vector<std::string>{},
        py::arg("candidate_weights") = std::unordered_map<std::string, double>{},
        "Calculate weighted, explainable job compatibility"
    );
}
