import sys
from pathlib import Path

import pytest


build_dirs = [
    Path("cpp/build/Release"),
    Path("cpp/build"),
]
for directory in build_dirs:
    if directory.exists():
        sys.path.insert(0, str(directory.resolve()))

match_engine = pytest.importorskip("match_engine", reason="Build the pybind11 module before running the C++ contract test")


def test_cpp_week6_alias_and_related_matching():
    result = match_engine.calculate_match(
        ["C++20", "ISO 26262 (ASIL-D)", "MATLAB/Simulink", "System Integration"],
        ["C++", "ISO26262", "Software Integration"],
        ["Simulink"],
        {"C++20": 1.0, "ISO 26262 (ASIL-D)": 1.0, "MATLAB/Simulink": 1.0, "System Integration": 1.0},
    )
    assert result.score >= 65
    assert "C++" in result.matched_skills
    assert len(result.related_skills) >= 1
    assert len(result.details) == 4
