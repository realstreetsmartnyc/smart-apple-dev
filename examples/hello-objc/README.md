# hello-objc — Example Project

Generated with:

```bash
smart-apple-dev init hello-objc --lang objc
cd hello-objc
smart-apple-dev build --target macos
smart-apple-dev sign --ipa
```

See `scripts/demo.sh` for an automated version.

To regenerate:

```bash
rm -rf examples/hello-objc/hello-objc
smart-apple-dev init examples/hello-objc/hello-objc --lang objc
```
