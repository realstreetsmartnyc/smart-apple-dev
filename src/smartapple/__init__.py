"""smart-apple-dev: Cross-platform iOS/macOS development toolchain."""

__version__ = "1.0.0"
__all__ = ["cli"]

# Import all modules for auto-discovery
from .build import (
    BuildProvider, ProviderCapabilities, ProviderResult, ProviderRegistry,
    LocalProvider, SSHProvider, GitHubActionsProvider, AWSMacProvider,
    AzureMacProvider, CircleCIMacProvider, MacStadiumProvider,
    CodemagicProvider, BitriseProvider, JenkinsMacProvider,
    BuildJetProvider, NevercodeProvider,
    get_registry, get_provider, auto_detect_provider,
)
from .build.orchestrator import BuildOrchestrator, BuildResult
from .build.swift import SwiftBackend
from .build.cpp import CppBackend
from .build.rust import RustBackend
from .build.go import GoBackend
from .build.kotlin import KotlinBackend
from .build.objc import ObjCBackend
from .build.java import JavaBackend
from .build.python import PythonBackend
from .build.javascript import JavaScriptBackend
from .build.csharp import CSharpBackend
from .build.game import GameEngineBackend
from .dev_phases.planning import (
    DevelopmentPlanner, DesignSystemGenerator, TestingFramework,
    DebuggingTools, DeploymentAutomation, FrameworkDetector,
    DevelopmentPhase, Requirement, ArchitectureComponent,
    DesignAsset, TestCase, DebugSession, DeploymentConfig,
)
