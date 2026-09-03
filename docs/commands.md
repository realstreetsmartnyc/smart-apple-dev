# Commands

| Command | What |
|---------|------|
| `init <name> --lang <lang>` | Scaffold a project |
| `build [--target ios/macos/android/...] [--release] [--provider X]` | Build |
| `sign [--mode ad-hoc/identity/skip] [--ipa]` | Sign + package IPA |
| `install [--ipa <path>] [--apk <path>] [--device <udid>]` | Install to device |
| `devices [--platform all/ios/android]` | List connected devices |
| `info` | Platform, SDKs, tools |
| `sdk list \| install \| extract` | Manage Apple SDKs |
| `doctor [--install]` | Diagnose / auto-fix |
| `check` | Per-language tool availability |
| `provider list \| default \| add \| del \| list-instances` | Build/LLM providers |
| `agent [--provider X] [REQUEST]` | LLM agent (one-shot or REPL) |

See [`USER_GUIDE.md`](https://github.com/realstreetsmartnyc/smart-apple-dev/blob/main/USER_GUIDE.md) for the full flag reference.
