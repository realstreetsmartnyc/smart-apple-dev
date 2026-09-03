# Build providers

A *provider* is *where* the build runs. The local provider runs on the
current machine; the others dispatch to remote Macs or CI/CD.

| Provider | When to use |
|----------|-------------|
| `local` | Default. clang / ldid / SDK on your machine. |
| `ssh` | Remote Mac/Linux box (`--host`, `--user`). |
| `github-actions` | CI (auto-detected on macOS runners). |
| `aws-mac` | EC2 Mac instances. |
| `azure-mac` | Azure DevOps macOS agents. |
| `codemagic` | Codemagic CI/CD. |
| `bitrise` | Bitrise. |
| `buildjet` | BuildJet cloud Mac runners. |
| `macstadium` | MacStadium dedicated Mac. |
| `circleci-mac` | CircleCI macOS executors. |
| `jenkins` | Jenkins macOS agents. |
| `nevercode` | Nevercode. |

```bash
smart-apple-dev build --provider local
smart-apple-dev build --provider ssh --host mac.example.com
```

Run `smart-apple-dev provider list` for a live status of every provider
and its capabilities (build / sign / install / upload, supported languages
and targets, cost per build).
