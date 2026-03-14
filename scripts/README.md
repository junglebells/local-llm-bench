# Scripts

## qwen3.5-35b-a3b-toggle-thinking.py

Toggle thinking mode on/off for the Qwen3.5-35B-A3B model in LM Studio or oMLX.

### Why this exists

Qwen3.5-35B-A3B is an excellent model — fast, capable, and practical for local use on Apple Silicon. But it has thinking enabled by default, which adds significant delay before every response. For many use cases (coding agents, document classification, chat) the model is capable enough without thinking, and the extra latency is unwanted.

Disabling thinking is harder than it should be:

- **`/no_think` in the system prompt does not work.** The `/no_think` soft switch worked for Qwen3 models, but appears to have been removed in Qwen3.5. It has no effect on Qwen3.5-35B-A3B via LM Studio or oMLX.
- **Ollama's native API** supports `"think": false`, but LM Studio and oMLX use the OpenAI-compatible endpoint which has no such parameter.
- **The only reliable method** is to patch the model's chat template directly — which is what this script does.

We reverse-engineered this by trial and error. This script saves you that effort.

For benchmarking specifically, thinking also distorts results: the model burns tokens on invisible `<think>` blocks (sometimes producing zero visible output), and TTFT measurements include thinking time rather than just prefill.

### How it works

The Qwen3.5 chat template (`chat_template.jinja`) ends with a generation prompt that primes every model response:

```jinja
{%- if add_generation_prompt %}
    {{- '<|im_start|>assistant\n' }}
{%- endif %}
```

When thinking is enabled (default), the model naturally starts with a `<think>` block. To disable thinking, the script injects a **pre-closed** empty think block:

```jinja
{%- if add_generation_prompt %}
    {{- '<|im_start|>assistant\n' }}
    {{- '<think>\n\n</think>\n\n' }}
{%- endif %}
```

This tricks the model into believing the reasoning phase already happened, so it skips straight to visible output.

### Where the template lives

The script searches for `chat_template.jinja` in the standard model directories:

| Backend | Path |
|---|---|
| LM Studio | `~/.lmstudio/models/mlx-community/Qwen3.5-35B-A3B-4bit/chat_template.jinja` |
| oMLX | `~/.omlx/models/mlx-community/Qwen3.5-35B-A3B-4bit/chat_template.jinja` |

First match wins. Use `--models-dir` to override if your models are stored elsewhere.

### Usage

```bash
# Check current state
python3 scripts/qwen3.5-35b-a3b-toggle-thinking.py status

# Disable thinking
python3 scripts/qwen3.5-35b-a3b-toggle-thinking.py off

# Enable thinking
python3 scripts/qwen3.5-35b-a3b-toggle-thinking.py on

# Verify via API (sends a test request, checks for <think> in response)
python3 scripts/qwen3.5-35b-a3b-toggle-thinking.py verify

# Custom models directory
python3 scripts/qwen3.5-35b-a3b-toggle-thinking.py --models-dir /path/to/models status
```

After toggling, **reload the model** in LM Studio or oMLX for the change to take effect.

### Integration with bench.py

The benchmark tool has a `--no-think` flag that automates this:

```bash
python3 bench.py --backend lmstudio --model mlx-community/qwen3.5-35b-a3b --no-think
```

This backs up the template, patches it to disable thinking, runs the benchmark, and **always restores the original** — even on errors or Ctrl+C. The `verify` command in this script is useful for confirming the state independently.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LMSTUDIO_URL` | `http://localhost:1234` | Server URL used by the `verify` command |
