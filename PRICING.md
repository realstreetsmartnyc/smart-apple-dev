# Pricing

`smart-apple-dev` is **MIT-licensed and free forever** for self-hosted use.
Paid options are opt-in services for teams that want managed infrastructure.

## Free (MIT, self-hosted)

| Feature | Included |
|---------|----------|
| CLI + all 11 commands | :white_check_mark: |
| All 21 LLM providers (BYOK or local) | :white_check_mark: |
| All 12 build providers | :white_check_mark: |
| Templates (7 stable + 5 experimental) | :white_check_mark: |
| Community support (GitHub Issues/Discussions) | :white_check_mark: |

You bring your own Mac, your own LLM API keys, your own certs. No account required.

## Cloud Build (coming soon)

Managed Mac mini pool — no Mac required.

| Plan | Price | Minutes/mo | Concurrency |
|------|-------|------------|-------------|
| Free | $0 | 100 | 1 |
| Starter | $19/mo | 500 | 2 |
| Team | $49/mo | 2000 | 4 |
| Enterprise | Custom | Unlimited | Custom |

- Billed per build-minute, 1-minute minimum.
- Powered by `smart-apple-dev provider use buildjet` / `macstadium` under the hood.
- Sign up: `smart-apple-dev provider add cloud --api-key $TOKEN` (once live).

## LLM Gateway (coming soon)

One API key, 21 providers, normalized OpenAI-compatible endpoint.

| Plan | Price | Included tokens |
|------|-------|-----------------|
| Free | $0 | 100K tokens |
| Starter | $10/mo | 2M tokens |
| Scale | $0.001 / 1K tokens | Pay as you go |

- Endpoint: `https://api.smart-apple-dev.com/v1`
- Use as `gateway:cloud` provider: `smart-apple-dev agent --provider gateway:cloud`

## Sponsorship

Support the project directly:

- [GitHub Sponsors](https://github.com/sponsors/smart-apple-dev) — $10 / $50 / $500 per month
- [Polar](https://polar.sh/smart-apple-dev) — fund specific feature bounties
- [Open Collective](https://opencollective.com/smart-apple-dev) — transparent finances

Sponsors are listed in README and get priority on feature requests.

## Enterprise

- Custom provider integrations (your CI, your MDM)
- 24h SLA support
- On-premise deployment help
- Contact: enterprise@smart-apple-dev.com

## Affiliate Disclosure

Some links to MacStadium, BuildJet, Codemagic, OpenRouter, and Together AI are affiliate links (marked with *). We earn a small commission at no extra cost to you. This helps fund the free tier.
