cmake_minimum_required(VERSION 3.15)

project(CareerCopilotMatchEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(
    Python
    COMPONENTS Interpreter Development
    REQUIRED
)

find_package(
    pybind11
    CONFIG
    REQUIRED
)

pybind11_add_module(
    match_engine
    match_engine.cpp
)