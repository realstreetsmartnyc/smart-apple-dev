"""Tests for development planning module (smartapple.dev_phases.planning)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from smartapple.dev_phases.planning import (
    ArchitectureComponent,
    DebugSession,
    DebuggingTools,
    DeploymentAutomation,
    DeploymentConfig,
    DesignAsset,
    DesignSystemGenerator,
    DevelopmentPhase,
    DevelopmentPlanner,
    FrameworkDetector,
    Requirement,
    TestCase,
    TestingFramework,
)


def test_development_phase_enum():
    """Verify enum members and values."""
    assert DevelopmentPhase.PLANNING.value == "planning"
    assert DevelopmentPhase.DESIGN.value == "design"
    assert DevelopmentPhase.DEVELOPMENT.value == "development"
    assert DevelopmentPhase.TESTING.value == "testing"
    assert DevelopmentPhase.DEBUGGING.value == "debugging"
    assert DevelopmentPhase.DEPLOYMENT.value == "deployment"
    assert DevelopmentPhase.MONITORING.value == "monitoring"


def test_data_classes_initialization(tmp_path):
    """Verify initialization and defaults of dataclasses."""
    req = Requirement(
        id="req_1",
        title="Test Req",
        description="Desc",
        priority="high",
        category="functional",
        acceptance_criteria=["AC1"],
    )
    assert req.status == "pending"
    assert req.dependencies == []
    assert req.acceptance_criteria == ["AC1"]

    arch = ArchitectureComponent(
        name="NetworkLayer",
        type="service",
        description="Handles HTTP requests",
        technologies=["URLSession"],
    )
    assert arch.dependencies == []
    assert arch.technologies == ["URLSession"]

    asset = DesignAsset(
        name="MainIcon",
        type="png",
        path=tmp_path / "icon.png",
    )
    assert asset.components == []
    assert asset.variants == []
    assert asset.dimensions == {}

    tc = TestCase(
        id="test_1",
        name="Login Test",
        description="Verify user login",
        type="unit",
        platform="ios",
        automation="xctest",
        steps=["Step 1"],
    )
    assert tc.prerequisites == []
    assert tc.steps == ["Step 1"]

    debug_session = DebugSession(
        id="dbg_1",
        timestamp=datetime.now(),
        issue_type="crash",
        severity="critical",
    )
    assert debug_session.status == "active"
    assert debug_session.affected_build == ""

    deploy_config = DeploymentConfig(
        target="app_store",
        distribution_type="ipa",
        release_channel="stable",
    )
    assert deploy_config.auto_publish is False
    assert deploy_config.review_required is True


def test_development_planner_creators(tmp_path):
    """Test DevelopmentPlanner factory methods."""
    planner = DevelopmentPlanner(tmp_path)

    req = planner.create_requirement("Auth", "User auth", "high", "functional", ["Must log in"])
    assert req.id == "req_1"
    assert len(planner.requirements) == 1

    arch = planner.create_architecture("DB", "layer", "SQLite storage", ["SQLite"])
    assert arch.name == "DB"
    assert len(planner.architecture) == 1

    asset = planner.create_design_asset("Logo", "svg", tmp_path / "logo.svg")
    assert asset.name == "Logo"
    assert len(planner.design_assets) == 1

    tc = planner.create_test_case("Auth Test", "Test Auth", "unit", "ios", "xctest", ["Step 1"])
    assert tc.id == "test_1"
    assert len(planner.test_cases) == 1


def test_development_planner_generate_phase_plan_without_config(tmp_path):
    """Test generate_phase_plan when config is None."""
    planner = DevelopmentPlanner(tmp_path)

    for phase in DevelopmentPhase:
        plan = planner.generate_phase_plan(phase)
        assert plan["phase"] == phase.value
        assert plan["project_info"]["name"] == ""
        assert plan["project_info"]["language"] == ""
        assert plan["project_info"]["target"] == "ios"
        assert isinstance(plan["tools"], list)
        assert isinstance(plan["checklists"], list)
        assert isinstance(plan["estimated_duration"], int)
        assert isinstance(plan["dependencies"], list)


def test_development_planner_generate_phase_plan_with_config(tmp_path):
    """Test generate_phase_plan when config is loaded."""
    config_file = tmp_path / "smartapple.toml"
    config_file.write_text('[project]\nname = "TestApp"\nlanguage = "swift"\ntarget = "macos"\n')

    planner = DevelopmentPlanner(tmp_path)
    planner.load_project_config()

    plan = planner.generate_phase_plan(DevelopmentPhase.PLANNING)
    assert plan["project_info"]["name"] == "TestApp"
    assert plan["project_info"]["language"] == "swift"
    assert plan["project_info"]["target"] == "macos"
    assert len(plan["tools"]) == 4
    assert len(plan["checklists"]) == 5
    assert plan["estimated_duration"] == 5
    assert plan["dependencies"] == []


def test_development_planner_export_plan(tmp_path):
    """Test exporting phase plan to JSON string."""
    planner = DevelopmentPlanner(tmp_path)
    json_str = planner.export_plan(DevelopmentPhase.DEVELOPMENT)

    data = json.loads(json_str)
    assert data["phase"] == "development"
    assert data["estimated_duration"] == 30
    assert data["dependencies"] == ["design"]


def test_design_system_generator(tmp_path):
    """Test DesignSystemGenerator UI kit generation."""
    generator = DesignSystemGenerator(tmp_path)

    ios_kit = generator.generate_ios_ui_kit(["Button", "Label"])
    assert (ios_kit / "button.swift").exists()
    assert (ios_kit / "label.swift").exists()
    assert (ios_kit / "Images.xcassets").is_dir()
    assert (ios_kit / "Colors.xccolors").exists()

    macos_kit = generator.generate_macos_ui_kit(["Button"])
    assert (macos_kit / "button.swift").exists()


def test_testing_framework(tmp_path):
    """Test TestingFramework setup methods."""
    tf = TestingFramework(tmp_path)

    xctest_dir = tf.setup_xctest("CustomTests")
    assert (xctest_dir / "Info.plist").exists()
    assert (xctest_dir / "SampleTests.swift").exists()

    uitest_dir = tf.setup_uitest("com.example.app")
    config_file = uitest_dir / "appium_config.json"
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data["app"] == "com.example.app"


def test_debugging_tools(tmp_path):
    """Test DebuggingTools file generations."""
    dt = DebuggingTools(tmp_path)

    crash_config = dt.create_crashlytics_config()
    assert crash_config.exists()
    assert "firebase_crashlytics_collection_enabled" in crash_config.read_text()

    instruments_scheme = dt.create_instruments_scheme("MyProject")
    assert instruments_scheme.exists()
    assert "MyProject Performance Profile" in instruments_scheme.read_text()

    console_script = dt.create_xcode_console_script("debug_script")
    assert console_script.exists()
    assert "=== Memory Analysis ===" in console_script.read_text()


def test_deployment_automation(tmp_path):
    """Test DeploymentAutomation Fastlane and Connect config generation."""
    da = DeploymentAutomation(tmp_path)

    fastfile = da.create_fastlane_config("123456")
    assert fastfile.exists()
    appfile = fastfile.parent / "Appfile"
    assert appfile.exists()
    assert "123456" in appfile.read_text()

    connect_config = da.create_app_store_connect_config("123456")
    assert connect_config.exists()
    data = json.loads(connect_config.read_text())
    assert data["app_id"] == "123456"


def test_framework_detector(tmp_path):
    """Test FrameworkDetector detection and auto-configuration."""
    (tmp_path / "Package.swift").write_text("import SwiftUI\n")
    (tmp_path / "Info.plist").write_text("NSAppTrackingTransparencyUsageDescription")
    (tmp_path / "MyModel.xcdatamodeld").mkdir()
    (tmp_path / "Shaders.metal").write_text("// metal shader")

    detector = FrameworkDetector(tmp_path)
    detected = detector.detect_frameworks()

    assert detected.get("swiftui") is True
    assert detected.get("app_tracking_transparency") is True
    assert detected.get("core_data") is True
    assert detected.get("metal") is True

    config_dir = detector.auto_configure(detected)
    assert (config_dir / "xcode.plist").exists()
    assert (config_dir / "Package.swift").exists()
