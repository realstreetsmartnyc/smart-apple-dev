# Godot 4 Template

A minimal Godot 4 project that builds to macOS and iOS via Godot's
export presets.

## Layout

- `project.godot` — engine config (name, main scene, renderer)
- `Main.tscn` — entry-point scene with a Label
- `Main.gd` — script that prints "Hello from {{NAME}}!"
- `export_presets.cfg` — macOS + iOS export presets
- `icon.svg` — placeholder icon (replace with your own)

## Build (Linux or macOS host)

```bash
# Use the Godot 4 binary in your PATH
godot --headless --export-release "macOS" build/macos/MyGame.app
```

The exported `.app` is unsigned. For App Store distribution, run the
Xcode archive + `xcrun altool` upload on a Mac.

## Notes

- Godot iOS export produces an Xcode project, not a `.ipa`. You must
  open it on a Mac and run `xcodebuild archive`.
- The export_presets.cfg sets `binary_format/architecture="x86_64"` for macOS.
  Change to `arm64` for Apple Silicon or `universal` for both.
- The placeholder bundle ID is `com.example.{{NAME}}` — change it in
  `export_presets.cfg` and `project.godot` after `init`.
