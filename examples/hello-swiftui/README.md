# hello-swiftui

A complete SwiftUI app example with Combine, CoreData, CoreLocation, and notifications.

## What it shows
- `@main` SwiftUI `App` with NavigationStack
- AppDelegate bridge for older UIKit lifecycle
- Onboarding flow
- CoreData stack setup
- Combine-based networking
- App Tracking Transparency prompt

## Build

This is an example, not a CLI-scaffolded project. To use it:

```bash
# From inside this dir:
swift build                    # needs macOS + Xcode for full SwiftUI
# or
smart-apple-dev build --target macos
```

## Note

SwiftUI requires a Swift toolchain. The `xtool` project provides a Linux Swift
toolchain but does not implement all SwiftUI features. For production
SwiftUI apps, use a Mac.
