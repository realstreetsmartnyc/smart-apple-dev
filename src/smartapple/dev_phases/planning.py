"""Development planning and design tools for Apple app and game development.

Comprehensive tools covering all phases:
- Planning: Requirements, architecture, tech stack selection
- Design: UI/UX, wireframing, prototyping, design systems
- Development: Code scaffolding, component libraries, templates
- Testing: Unit, integration, UI, performance, automation
- Debugging: Crash reporting, profiling, diagnostics, analytics
- Deployment: CI/CD, app store automation, distribution
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from ..core.config import ProjectConfig
from ..build.provider import get_provider, get_registry, ProviderCapabilities


class DevelopmentPhase(Enum):
    PLANNING = "planning"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEBUGGING = "debugging"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"


@dataclass
class Requirement:
    """Development requirement definition."""
    id: str
    title: str
    description: str
    priority: str  # "high", "medium", "low"
    category: str  # "functional", "non-functional", "technical"
    status: str = "pending"  # "pending", "in-progress", "completed"
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class ArchitectureComponent:
    """Software architecture component."""
    name: str
    type: str  # "module", "service", "layer", "pattern"
    description: str
    dependencies: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)


@dataclass
class DesignAsset:
    """UI/UX design asset."""
    name: str
    type: str  # "figma", "sketch", "pdf", "png", "svg"
    path: Path
    components: list[str] = field(default_factory=list)
    variants: list[str] = field(default_factory=list)
    dimensions: dict[str, int] = field(default_factory=dict)


@dataclass
class TestCase:
    """Automated test case."""
    id: str
    name: str
    description: str
    type: str  # "unit", "integration", "ui", "performance", "security"
    platform: str  # "ios", "macos", "both"
    automation: str  # "xctest", "appium", "cypress", "mocha", "pytest"
    prerequisites: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class DebugSession:
    """Debugging session tracking."""
    id: str
    timestamp: datetime
    issue_type: str  # "crash", "performance", "memory", "network"
    severity: str  # "critical", "high", "medium", "low"
    status: str = "active"  # "active", "investigating", "resolved", "closed"
    affected_build: str = ""
    logs: list[str] = field(default_factory=list)
    stack_trace: str = ""
    device_info: dict[str, Any] = field(default_factory=dict)
    steps_to_reproduce: list[str] = field(default_factory=list)


@dataclass
class DeploymentConfig:
    """Deployment configuration."""
    target: str  # "app_store", "enterprise", "ad_hoc", "debug"
    distribution_type: str  # "ipa", "apk", "both"
    release_channel: str  # "stable", "beta", "alpha"
    auto_publish: bool = False
    review_required: bool = True
    beta_testers: list[str] = field(default_factory=list)
    app_store_ids: list[str] = field(default_factory=list)


class DevelopmentPlanner:
    """Plan and orchestrate Apple app/game development workflow."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.config: ProjectConfig | None = None
        self.requirements: list[Requirement] = []
        self.architecture: list[ArchitectureComponent] = []
        self.design_assets: list[DesignAsset] = []
        self.test_cases: list[TestCase] = []
        self.debug_sessions: list[DebugSession] = []
        self.deployments: list[DeploymentConfig] = []

    def load_project_config(self) -> ProjectConfig:
        from ..core.config import load_config
        self.config = load_config(self.project_dir)
        return self.config

    def create_requirement(self, title: str, description: str, priority: str,
                            category: str, acceptance_criteria: list[str] = None) -> Requirement:
        req_id = f"req_{len(self.requirements) + 1}"
        requirement = Requirement(
            id=req_id,
            title=title,
            description=description,
            priority=priority,
            category=category,
            acceptance_criteria=acceptance_criteria or []
        )
        self.requirements.append(requirement)
        return requirement

    def create_architecture(self, name: str, component_type: str,
                             description: str, technologies: list[str] = None) -> ArchitectureComponent:
        component = ArchitectureComponent(
            name=name,
            type=component_type,
            description=description,
            technologies=technologies or []
        )
        self.architecture.append(component)
        return component

    def create_design_asset(self, name: str, asset_type: str, path: Path) -> DesignAsset:
        asset = DesignAsset(
            name=name,
            type=asset_type,
            path=path
        )
        self.design_assets.append(asset)
        return asset

    def create_test_case(self, name: str, description: str, test_type: str,
                         platform: str, automation: str, steps: list[str] = None) -> TestCase:
        test_id = f"test_{len(self.test_cases) + 1}"
        test_case = TestCase(
            id=test_id,
            name=name,
            description=description,
            type=test_type,
            platform=platform,
            automation=automation,
            steps=steps or []
        )
        self.test_cases.append(test_case)
        return test_case

    def generate_phase_plan(self, phase: DevelopmentPhase) -> dict[str, Any]:
        """Generate comprehensive plan for a development phase."""
        plan = {
            "phase": phase.value,
            "project_info": {
                "name": self.config.name if self.config else "",
                "language": self.config.language if self.config else "",
                "target": self.config.target if self.config else "ios",
            },
            "tasks": [],
            "tools": self._get_phase_tools(phase),
            "checklists": self._get_phase_checklists(phase),
            "estimated_duration": self._estimate_phase_duration(phase),
            "dependencies": self._get_phase_dependencies(phase),
        }
        return plan

    def _get_phase_tools(self, phase: DevelopmentPhase) -> list[dict[str, Any]]:
        """Get recommended tools for a phase."""
        tools = {
            DevelopmentPhase.PLANNING: [
                {"name": "Figma", "purpose": "UI/UX design", "platform": "web"},
                {"name": "Draw.io", "purpose": "Architecture diagrams", "platform": "web"},
                {"name": "Postman", "purpose": "API design", "platform": "desktop"},
                {"name": "Notion", "purpose": "Requirements documentation", "platform": "web"},
            ],
            DevelopmentPhase.DESIGN: [
                {"name": "Xcode Design", "purpose": "Native UI design", "platform": "macos"},
                {"name": "Sketch", "purpose": "App icons, splash screens", "platform": "macos"},
                {"name": "Principle", "purpose": "Interactive prototypes", "platform": "macos"},
            ],
            DevelopmentPhase.DEVELOPMENT: [
                {"name": "Xcode", "purpose": "Code editor", "platform": "macos"},
                {"name": "SwiftLint", "purpose": "Code quality", "platform": "cli"},
                {"name": "SonarQube", "purpose": "Static analysis", "platform": "server"},
            ],
            DevelopmentPhase.TESTING: [
                {"name": "XCTest", "purpose": "Unit testing", "platform": "macos"},
                {"name": "Appium", "purpose": "UI testing", "platform": "desktop"},
                {"name": "Xcode Organizer", "purpose": "Test reporting", "platform": "macos"},
            ],
            DevelopmentPhase.DEBUGGING: [
                {"name": "Instruments", "purpose": "Performance profiling", "platform": "macos"},
                {"name": "Crashlytics", "purpose": "Crash reporting", "platform": "server"},
                {"name": "Xcode Console", "purpose": "Real-time debugging", "platform": "macos"},
            ],
            DevelopmentPhase.DEPLOYMENT: [
                {"name": "Fastlane", "purpose": "App Store automation", "platform": "cli"},
                {"name": "Firebase App Distribution", "purpose": "Beta testing", "platform": "server"},
                {"name": "Xcode Cloud", "purpose": "CI/CD", "platform": "macos"},
            ],
        }
        return tools.get(phase, [])

    def _get_phase_checklists(self, phase: DevelopmentPhase) -> list[dict[str, Any]]:
        """Get phase-specific checklists."""
        checklists = {
            DevelopmentPhase.PLANNING: [
                {"item": "Define target audience", "critical": True},
                {"item": "Specify technical requirements", "critical": True},
                {"item": "Select tech stack", "critical": True},
                {"item": "Create project timeline", "critical": True},
                {"item": "Identify stakeholders", "critical": False},
            ],
            DevelopmentPhase.DESIGN: [
                {"item": "Create user flows", "critical": True},
                {"item": "Design wireframes", "critical": True},
                {"item": "Create UI components", "critical": True},
                {"item": "Design for accessibility", "critical": True},
                {"item": "Get stakeholder approval", "critical": True},
            ],
        }
        return checklists.get(phase, [])

    def _estimate_phase_duration(self, phase: DevelopmentPhase) -> int:
        """Estimate phase duration in days."""
        durations = {
            DevelopmentPhase.PLANNING: 5,
            DevelopmentPhase.DESIGN: 10,
            DevelopmentPhase.DEVELOPMENT: 30,
            DevelopmentPhase.TESTING: 7,
            DevelopmentPhase.DEBUGGING: 3,
            DevelopmentPhase.DEPLOYMENT: 2,
            DevelopmentPhase.MONITORING: 5,
        }
        return durations.get(phase, 5)

    def _get_phase_dependencies(self, phase: DevelopmentPhase) -> list[str]:
        """Get phase dependencies."""
        dependencies = {
            DevelopmentPhase.DESIGN: ["planning"],
            DevelopmentPhase.DEVELOPMENT: ["design"],
            DevelopmentPhase.TESTING: ["development"],
            DevelopmentPhase.DEBUGGING: ["testing"],
            DevelopmentPhase.DEPLOYMENT: ["development", "testing"],
            DevelopmentPhase.MONITORING: ["deployment"],
        }
        return dependencies.get(phase, [])

    def export_plan(self, phase: DevelopmentPhase) -> str:
        """Export development plan as JSON."""
        plan = self.generate_phase_plan(phase)
        return json.dumps(plan, indent=2)


class DesignSystemGenerator:
    """Generate design systems and component libraries for Apple platforms."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def generate_ios_ui_kit(self, components: list[str]) -> Path:
        """Generate iOS UI kit with native components."""
        kit_dir = self.project_dir / "ui_kit" / "ios"
        kit_dir.mkdir(parents=True, exist_ok=True)

        # Generate SwiftUI components
        for component in components:
            self._create_swiftui_component(kit_dir, component)

        # Generate asset catalogs
        self._create_asset_catalogs(kit_dir)

        return kit_dir

    def generate_macos_ui_kit(self, components: list[str]) -> Path:
        """Generate macOS UI kit with native components."""
        kit_dir = self.project_dir / "ui_kit" / "macos"
        kit_dir.mkdir(parents=True, exist_ok=True)

        # Generate AppKit components
        for component in components:
            self._create_appkit_component(kit_dir, component)

        return kit_dir

    def _create_swiftui_component(self, kit_dir: Path, component: str):
        """Create a SwiftUI component."""
        content = self._get_component_template(component, "swiftui")
        component_path = kit_dir / f"{component.lowercase()}.swift"
        component_path.write_text(content)

    def _create_appkit_component(self, kit_dir: Path, component: str):
        """Create an AppKit component."""
        content = self._get_component_template(component, "appkit")
        component_path = kit_dir / f"{component.lower_case()}.swift"
        component_path.write_text(content)

    def _get_component_template(self, component: str, framework: str) -> str:
        """Get component template."""
        templates = {
            "button": self._get_button_template(framework),
            "label": self._get_label_template(framework),
            "text_field": self._get_text_field_template(framework),
            "navigation_view": self._get_navigation_view_template(framework),
            "tab_view": self._get_tab_view_template(framework),
        }
        return templates.get(component, f"// {component.title()} component for {framework}")

    def _create_asset_catalogs(self, kit_dir: Path):
        """Create asset catalogs for iOS."""
        # Create Images.xcassets
        images_dir = kit_dir / "Images.xcassets"
        images_dir.mkdir(exist_ok=True)

        # Create Colors.xccolors
        colors_path = kit_dir / "Colors.xccolors"
        colors_content = self._get_colors_content()
        colors_path.write_text(colors_content)

    def _get_colors_content(self) -> str:
        """Get iOS color definitions."""
        return """{
    "colors" : [
        {
            "color" : {
                "color-space" : "sRGB",
                "color" : {
                    "components" : {
                        "red" : "0.0",
                        "green" : "0.0",
                        "blue" : "0.0",
                        "alpha" : "1.0"
                    }
                }
            },
            "id" : "systemBackground",
            "palette-name" : "system"
        },
        {
            "color" : {
                "color-space" : "sRGB",
                "color" : {
                    "components" : {
                        "red" : "0.0",
                        "green" : "0.0",
                        "blue" : "0.5",
                        "alpha" : "1.0"
                    }
                }
            },
            "id" : "systemBlue",
            "palette-name" : "system"
        }
    ]
}"""


class TestingFramework:
    """Generate and manage testing frameworks for Apple platforms."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def setup_xctest(self, test_target: str = "MyAppTests") -> Path:
        """Set up XCTest framework for unit testing."""
        test_dir = self.project_dir / test_target
        test_dir.mkdir(exist_ok=True)

        # Create Info.plist for test target
        self._create_test_info_plist(test_dir)

        # Create sample test cases
        self._create_sample_tests(test_dir)

        return test_dir

    def setup_uitest(self, bundle_id: str) -> Path:
        """Set up UI testing with Appium/XCTest."""
        uitest_dir = self.project_dir / "UITests"
        uitest_dir.mkdir(exist_ok=True)

        # Create configuration
        self._create_uitest_config(uitest_dir, bundle_id)

        return uitest_dir

    def _create_test_info_plist(self, test_dir: Path):
        """Create Info.plist for test target."""
        content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>$(DEVELOPMENT_LANGUAGE)</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>BNDL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>XCTestBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
</dict>
</plist>"""
        (test_dir / "Info.plist").write_text(content)

    def _create_sample_tests(self, test_dir: Path):
        """Create sample test cases."""
        sample_test = test_dir / "SampleTests.swift"
        content = """import XCTest

class SampleTests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    func testExample() {
        // This is an example of a functional test case.
        XCTAssert(true, "Pass")
    }

    func testPerformanceExample() {
        // This is an example of a performance test case.
        measure {
            // Code that will be measured for performance.
        }
    }
}"""
        sample_test.write_text(content)

    def _create_uitest_config(self, uitest_dir: Path, bundle_id: str):
        """Create UI test configuration."""
        config = uitest_dir / "appium_config.json"
        content = json.dumps({
            "platformName": "iOS",
            "automationName": "XCTest",
            "app": bundle_id,
            "deviceName": "iPhone Simulator",
            "platformVersion": "latest",
            "xcodeOrgId": "YOUR_XCODE_ORG_ID",
            "xcodeSigningId": "iPhone Developer",
            "udid": "SIMULATOR_UDID"
        }, indent=2)
        config.write_text(content)


class DebuggingTools:
    """Comprehensive debugging and diagnostics tools."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def create_crashlytics_config(self) -> Path:
        """Create Crashlytics configuration."""
        config_dir = self.project_dir / ".firebase"
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / "crashlytics.properties"
        content = """# Crashlytics Configuration
firebase_crashlytics_collection_enabled=true
firebase_crashlytics_analytics_enabled=true
firebase_crashlytics_testing_enabled=false
firebase_crashlytics_auto_collection_enabled=true
firebase_crashlytics_debug_enabled=false
"""
        config_file.write_text(content)

        return config_file

    def create_instruments_scheme(self, project_name: str) -> Path:
        """Create Instruments profiling scheme."""
        scheme_dir = self.project_dir / "profiling"
        scheme_dir.mkdir(exist_ok=True)

        scheme_file = scheme_dir / "performance.instruments"
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{project_name} Performance Profile</string>
    <key>Instrument</key>
    <string>Time Profiler</string>
    <key>ShowLaunchTime</key>
    <true/>
    <key>ShowCPUUsage</key>
    <true/>
    <key>ShowMemoryAllocations</key>
    <true/>
    <key>ShowCustomInstruments</key>
    <true/>
    <key>CustomInstruments</key>
    <array>
        <dict>
            <key>Identifier</key>
            <string>com.apple.instruments.GC.GCAlloc</string>
            <key>DisplayName</key>
            <string>Garbage Collection Allocations</string>
        </dict>
    </array>
</dict>
</plist>"""
        scheme_file.write_text(content)

        return scheme_file

    def create_xcode_console_script(self, script_name: str) -> Path:
        """Create Xcode console debugging script."""
        script_dir = self.project_dir / "scripts"
        script_dir.mkdir(exist_ok=True)

        script_file = script_dir / f"{script_name}.xcconsole"
        content = """# Xcode Console Script
# Debugging and diagnostics commands

# Memory analysis
print "=== Memory Analysis ==="
malloc_history -c 50
alloc_history -c 50

# CPU analysis
thread_time -c 50
cpu_load -c 60

# Performance metrics
time_profile -c 30
energy_metrics -c 30

# Network analysis
network_data -c 30

# App lifecycle
task_info -c 30
"""
        script_file.write_text(content)

        return script_file


class DeploymentAutomation:
    """App Store and distribution automation."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def create_fastlane_config(self, app_store_id: str) -> Path:
        """Create Fastlane configuration for App Store deployment."""
        fastlane_dir = self.project_dir / "fastlane"
        fastlane_dir.mkdir(exist_ok=True)

        # generateappfile
        appfile = fastlane_dir / "Appfile"
        appfile_content = f"""app_identifier "com.example.{self.project_dir.name}"
apple_id "{app_store_id}"
team_id "YOUR_TEAM_ID"
skip_confirm "true"
"""
        appfile.write_text(appfile_content)

        # Fastfile
        fastfile = fastlane_dir / "Fastfile"
        fastfile_content = self._get_fastfile_content(app_store_id)
        fastfile.write_text(fastfile_content)

        return fastfile

    def _get_fastfile_content(self, app_store_id: str) -> str:
        """Get Fastfile content with all necessary lanes."""
        project_name = self.project_dir.name
        return f"""default_platform :ios

# BETA LANES
beta do
  pod_update
  gym
  sigh
  pilot
  messaging
end

# PRODUCTION LANES
production do
  ensure_bundle_version
  gym
  notary
  deliver
  promote
end

# INTERNAL DISTRIBUTION LANES
internal do
  gym
  sigh
  deploy_to_testflight
end

# ALPHA RELEASE LANES
alpha do
  ensure_bundle_version
  gym
  sigh
  pilot
  messaging
  deploy_to_testflight
end

# SYNC LANES
sync do
  detect_provided_by_gem "fastlane"
  pilot
  gym
  sync_snapshots
end

before_all do
  # Prepare environment
  FileUtils.rm("fastlane/report.xml") if FileUtils.exist?("fastlane/report.xml")
  FileUtils.rm("fastlane/lane.log") if FileUtils.exist?("fastlane/lane.log")
end

after_all do
  # Clean up
  FileUtils.rm("fastlane/lane.log") if FileUtils.exist?("fastlane/lane.log")
end
"""

    def create_app_store_connect_config(self, app_store_id: str) -> Path:
        """Create App Store Connect API configuration."""
        config_dir = self.project_dir / ".app_store_connect"
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / "connect_config.json"
        content = json.dumps({
            "app_id": app_store_id,
            "api_key_id": "YOUR_API_KEY_ID",
            "issuer_id": "YOUR_ISSUER_ID",
            "key_id": "YOUR_KEY_ID",
            "private_key": "-----BEGIN PRIVATE KEY-----\\nYOUR_PRIVATE_KEY\\n-----END PRIVATE KEY-----",
            "environment": "production",
            "release_type": "immediate",
            "submitted": False,
            "uploaded_assets": []
        }, indent=2)
        config_file.write_text(content)

        return config_file


class FrameworkDetector:
    """Detect and auto-configure development frameworks."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def detect_frameworks(self) -> dict[str, Any]:
        """Detect available frameworks and auto-configure."""
        frameworks = {
            "swiftui": self._detect_swiftui,
            "combine": self._detect_combine,
            "core_data": self._detect_core_data,
            "core_motion": self._detect_core_motion,
            "metal": self._detect_metal,
            "arkit": self._detect_arkit,
            "cloud_kit": self._detect_cloud_kit,
            "user_notifications": self._detect_user_notifications,
            "push_notifications": self._detect_push_notifications,
            "app_tracking_transparency": self._detect_att,
        }

        detected = {}
        for framework, detector in frameworks.items():
            if detector():
                detected[framework] = True

        return detected

    def auto_configure(self, detected_frameworks: dict[str, Any]) -> Path:
        """Auto-configure project with detected frameworks."""
        config_dir = self.project_dir / "FrameworkConfig"
        config_dir.mkdir(exist_ok=True)

        # Generate .xcode.plist with framework configurations
        xcode_plist = config_dir / "xcode.plist"
        xcode_content = self._generate_xcode_plist(detected_frameworks)
        xcode_plist.write_text(xcode_content)

        # Generate Swift package dependencies
        package_path = config_dir / "Package.swift"
        package_content = self._generate_package_swift(detected_frameworks)
        package_path.write_text(package_content)

        return config_dir

    def _detect_swiftui(self) -> bool:
        """Detect SwiftUI usage."""
        return (self.project_dir / "Package.swift").exists() and \
               "SwiftUI" in (self.project_dir / "Package.swift").read_text()

    def _detect_combine(self) -> bool:
        """Detect Combine framework usage."""
        return True  # Always available in modern Xcode

    def _detect_core_data(self) -> bool:
        """Detect Core Data model files."""
        return any(self.project_dir.rglob("*.xcdatamodeld"))

    def _detect_core_motion(self) -> bool:
        """Detect motion sensor usage."""
        return any(".coremotion" in str(p) for p in self.project_dir.rglob("*"))

    def _detect_metal(self) -> bool:
        """Detect Metal shader files."""
        return any(p.suffix == ".metal" for p in self.project_dir.rglob("*"))

    def _detect_arkit(self) -> bool:
        """Detect ARKit usage."""
        return any("arkit" in str(p).lower() for p in self.project_dir.rglob("*"))

    def _detect_cloud_kit(self) -> bool:
        """Detect CloudKit usage."""
        return any("cloudkit" in str(p).lower() for p in self.project_dir.rglob("*"))

    def _detect_user_notifications(self) -> bool:
        """Detect UserNotifications usage."""
        return True  # Foundation for iOS 10+

    def _detect_push_notifications(self) -> bool:
        """Detect PushNotifications usage."""
        return True  # Foundation for iOS 10+

    def _detect_att(self) -> bool:
        """Detect App Tracking Transparency."""
        return (self.project_dir / "Info.plist").exists() and \
               "NSAppTrackingTransparencyUsageDescription" in (self.project_dir / "Info.plist").read_text()

    def _generate_xcode_plist(self, frameworks: dict[str, Any]) -> str:
        """Generate xcode.plist with framework settings."""
        enabled_frameworks = [fw for fw, enabled in frameworks.items() if enabled]
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>AvailableLibraries</key>
    <array>
{"".join(f"        <string>{fw}</string>\\n" for fw in enabled_frameworks)}
    </array>
    <key>RequiredDeviceCapabilities</key>
    <array>
        <string>arm64</string>
    </array>
    <key>MinimumOSVersion</key>
    <string>15.0</string>
</dict>
</plist>"""

    def _generate_package_swift(self, frameworks: dict[str, Any]) -> str:
        """Generate Package.swift with framework dependencies."""
        dependencies = []
        if frameworks.get("swiftui"):
            dependencies.append('.package(url: "https://github.com/SwiftUI/Xcode", from: "1.0.0")')

        return f"""// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "{self.project_dir.name}",
    platforms: [.iOS(.v15), .macOS(.v12)],
    products: [
        .library(
            name: "{self.project_dir.name}",
            targets: ["{self.project_dir.name}"]),
    ],
    dependencies: [
        {"".join(f"        {dep}\\n" for dep in dependencies)},
    ],
    targets: [
        .target(
            name: "{self.project_dir.name}",
            dependencies: []),
        .testTarget(
            name: "{self.project_dir.name}Tests",
            dependencies: ["{self.project_dir.name}"]),
    ]
)
"""
