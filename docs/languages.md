# Languages

`smart-apple-dev init` accepts `--lang` with any of:

| Language | Template | Backend | Apple | Android |
|----------|----------|---------|-------|---------|
| Swift | `swift` | `swift.py` (xtool) | ✅ | — |
| Objective-C | `objc` | `objc.py` | ✅ | — |
| C / C++ | `cpp` | `cpp.py` (clang + ld64.lld) | ✅ | — |
| Rust | `rust` | `rust.py` (cargo + cross-linker) | ✅ | — |
| Go | `go` | `go.py` | ✅ | — |
| Kotlin | `kotlin` | `kotlin.py` (Gradle) | ✅ | ✅ |

Experimental (work in progress):

| Language | Template | Backend |
|----------|----------|---------|
| SwiftUI / watchOS / tvOS / visionOS | `swiftui`, `watchos`, `tvos`, `visionos` | swift (xtool) |
| JavaScript / TypeScript | `javascript`, `typescript` | `javascript.py` 🟡 |
| Java | `java` | `java.py` 🟡 |
| Python | `python` | `python.py` 🟡 |
| C# | `csharp` | `csharp.py` 🟡 |
| Godot / Unity / Unreal | `godot`, `unity`, `unreal` | `game.py` 🟡 |

## Custom targets

Every backend is a Python class in `src/smartapple/build/<lang>.py`. To add a
new language, copy the closest existing one and adjust the compiler
invocation. See [`ARCHITECTURE.md`](https://github.com/realstreetsmartnyc/smart-apple-dev/blob/main/ARCHITECTURE.md).
