# Firebase C++ SDK Configuration for smart-apple-dev C++ projects
# Add Firebase C++ dependencies to CMakeLists.txt

cmake_minimum_required(VERSION 3.14)
project({{NAME}} LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

add_executable({{NAME}} main.cpp)

# Firebase C++ SDK
# Install: git clone https://github.com/firebase/firebase-cpp-sdk.git
# Or use vcpkg: vcpkg install firebase

# Firebase App Check
target_link_libraries({{NAME}} PRIVATE firebase_app_check)

# Analytics (optional)
# target_link_libraries({{NAME}} PRIVATE firebase_analytics)

# Auth (optional)
# target_link_libraries({{NAME}} PRIVATE firebase_auth)

# Firestore (optional)
# target_link_libraries({{NAME}} PRIVATE firebase_firestore)

# Storage (optional)
# target_link_libraries({{NAME}} PRIVATE firebase_storage)

# Messaging (optional)
# target_link_libraries({{NAME}} PRIVATE firebase_messaging)

# Dynamic Links (optional)
# target_link_libraries({{NAME}} PRIVATE firebase_dynamic_links)

# Include Google Services framework
target_link_libraries({{NAME}} PRIVATE framework.google)