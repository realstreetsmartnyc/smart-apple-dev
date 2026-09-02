"""smart-apple-dev build module - providers and backends for iOS/macOS development."""

# Re-export provider classes
from .provider import (
    BuildProvider,
    ProviderCapabilities,
    ProviderResult,
    ProviderRegistry,
    LocalProvider,
    SSHProvider,
    GitHubActionsProvider,
    AWSMacProvider,
    AzureMacProvider,
    CircleCIMacProvider,
    MacStadiumProvider,
    CodemagicProvider,
    BitriseProvider,
    JenkinsMacProvider,
    BuildJetProvider,
    NevercodeProvider,
    get_registry,
    get_provider,
    auto_detect_provider,
)

# Re-export backend classes
from .orchestrator import BuildOrchestrator, BuildResult

__all__ = [
    # Providers
    "BuildProvider",
    "ProviderCapabilities",
    "ProviderResult",
    "ProviderRegistry",
    "LocalProvider",
    "SSHProvider",
    "GitHubActionsProvider",
    "AWSMacProvider",
    "AzureMacProvider",
    "CircleCIMacProvider",
    "MacStadiumProvider",
    "CodemagicProvider",
    "BitriseProvider",
    "JenkinsMacProvider",
    "BuildJetProvider",
    "NevercodeProvider",
    "get_registry",
    "get_provider",
    "auto_detect_provider",
    # Orchestrator
    "BuildOrchestrator",
    "BuildResult",
]