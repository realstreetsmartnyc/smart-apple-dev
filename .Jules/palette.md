## 2025-02-18 - Standard NO_COLOR Support for CLI Accessibility
**Learning:** App-specific color disable flags like `SMART_APPLE_DEV_NO_COLOR` miss standard accessibility preferences set by screen readers and CLI users via `NO_COLOR` (https://no-color.org/).
**Action:** Always check both standard `NO_COLOR` and app-specific no-color environment variables in CLI UI modules.
