# LLM agent

21 LLM providers, one interface. Use `base:label` to keep multiple accounts.

## Quickstart

```bash
# List all 21 providers
smart-apple-dev agent --provider list

# Local (no API key)
smart-apple-dev agent --provider ollama "what's the build error?"
smart-apple-dev agent --provider lmstudio "add dark mode"

# Cloud (set API key env var)
export ANTHROPIC_API_KEY=sk-...
smart-apple-dev agent --provider anthropic "refactor this"
```

## Named instances

Configure multiple accounts of the same provider:

```bash
smart-apple-dev provider add copilot:default --api-key $GITHUB_TOKEN
smart-apple-dev provider add custom:openrouter \
    --base-url https://openrouter.ai/api/v1 --api-key $OR_KEY
smart-apple-dev provider list-instances
smart-apple-dev agent --provider copilot:default "ship it"
```

## The agent loop

`smart-apple-dev agent` runs a tool-using agent with 10 tools:

- `doctor`, `build`, `sign`, `install`, `sdk_list`
- `read_file`, `write_file`, `run_shell`
- `provider_list`, `ask_user`

Shell access has an allowlist/blocklist for safety.

## Deterministic mode (CI / tests)

```bash
smart-apple-dev agent --provider none --plan plan.json "build and sign"
```

## Supported bases

`anthropic`, `openai`, `groq`, `mistral`, `together`, `xai`, `deepseek`,
`perplexity`, `copilot`, `gemini`, `opencode`, `nous`, `sambanova`,
`cline`, `kilo`, `gateway`, `minimax`, `ollama`, `lmstudio`, `custom`,
`none`.
