# local-llm-bench

Scenario-based LLM benchmark for Apple Silicon. Measures what you actually wait for, not just the generation tok/s counter.

Your LLM UI says *"57 tok/s"*. But every response starts with a **prefill phase** where the model processes your entire conversation history before the first token appears. As context grows, prefill dominates. A model reporting 57 tok/s can deliver as low as 3 tok/s in practice.

This benchmark measures **effective throughput**: output tokens divided by total wall-clock time. The speed you experience, not the speed on screen. It runs real conversation scenarios (agent workflows, document classification, creative writing) and compares backends, engines, and hardware on the same workloads.

```
effective tok/s = output_tokens / (prefill_time + generation_time)
```

[Full analysis: MLX vs llama.cpp on Apple Silicon](https://famstack.dev/guides/mlx-vs-gguf-apple-silicon) | [Discord](https://discord.gg/tT54FNyf) | [Bluesky](https://bsky.app/profile/famstack.dev) | [Reddit](https://www.reddit.com/user/arthware/)

## Quick Start

Python 3.8+, no dependencies. Just a running inference backend with a model loaded.

```bash
# Ollama (default)
python3 bench.py --model llama3.1:8b

# LM Studio
python3 bench.py --backend lmstudio --model mlx-community/qwen3.5-35b-a3b --no-think

# oMLX or any OpenAI-compatible endpoint
OPENAI_API_KEY=key python3 bench.py --backend openai --backend-label omlx \
  --base-url http://localhost:8000 --model "Qwen3.5-35B-A3B-4bit" --no-think

# Compare results
python3 compare.py results/<model>/<scenario>/*.json
```

Results auto-save to `results/<model>/<scenario>/<chip>_<backend>.json`.

> **Before you run:** Set your context window to at least **16K tokens**. Add `--no-think` for Qwen3.5 models. **[Setup Guide -->](docs/setup-guide.md)**

## Results

Effective tok/s (**bold**) with generation tok/s in parentheses. Higher is better.

### Qwen3.5-35B-A3B (4-bit, thinking disabled)

| Hardware | Backend | ops-agent | doc-summary | prefill-test | creative-writing |
|---|---|---:|---:|---:|---:|
| M1 Max (64GB, 24 GPU) | oMLX | **34.6** (53.3) | **25.7** (55.5) | **30.0** (52.0) | **51.5** (56.2) |
| M1 Max (64GB, 24 GPU) | LM Studio MLX | **17.0** (56.6) | **13.4** (56.8) | **5.9** (54.4) | **38.3** (58.9) |
| M1 Max (64GB, 24 GPU) | LM Studio GGUF | **17.6** (28.2) | **19.4** (29.3) | **7.8** (28.4) | **27.7** (28.6) |

[oMLX](https://github.com/jundot/omlx) wins every scenario. Generation speed is identical to LM Studio MLX (~55 tok/s), but prefill is **up to 10x faster** thanks to its tiered KV cache. At 8K context, LM Studio takes 49s to prefill. oMLX takes 1.7s.

### Llama 3.1 8B (4-bit)

| Hardware | Backend | ops-agent | doc-summary | prefill-test | creative-writing |
|---|---|---:|---:|---:|---:|
| M1 Max (64GB, 24 GPU) | LM Studio MLX | **40.7** (55.0) | **21.9** (59.6) | **8.4** (51.8) | **58.9** (62.1) |
| M1 Max (64GB, 24 GPU) | LM Studio GGUF | **30.6** (36.4) | **18.5** (40.7) | **7.1** (33.4) | **38.1** (39.1) |
| M1 Max (64GB, 24 GPU) | Ollama GGUF | **27.1** (33.4) | **18.9** (37.8) | **5.8** (30.7) | **38.6** (39.6) |

At 8B, MLX wins across the board. The model is small enough that prefill stays fast and the 1.5x generation speed advantage dominates.

### Help fill this table

> Run `python3 bench.py --model llama3.1:8b` and [open a PR](#contribute-your-results). Five minutes, no dependencies.

| Hardware | Backend | ops-agent | doc-summary | prefill-test | creative-writing |
|---|---|---:|---:|---:|---:|
| M1 Max (64GB, 24 GPU) | Ollama GGUF | **27.1** (33.4) | **18.9** (37.8) | **5.8** (30.7) | **38.6** (39.6) |
| M2 Pro / Max | | | | | |
| M3 / Pro / Max | | | | | |
| M4 / Pro / Max | | | | | |

## Scenarios

Four real-world scenarios. All run by default, or pick one with `--scenario`.

| Scenario | Mode | What it tests |
|---|---|---|
| [ops-agent](scenarios/ops-agent.json) | 8-turn conversation | Agent with tool calls. Context grows every turn. |
| [doc-summary](scenarios/doc-summary.json) | 5 single-shot turns | Document classification. Long input, short output. |
| [prefill-test](scenarios/prefill-test.json) | 4 single-shot turns | Prefill scaling: 655 to 8.5K context, same short reply. |
| [creative-writing](scenarios/creative-writing.json) | 3 single-shot turns | Short prompt, long output (up to 2K tokens). |

You can [create your own scenarios](docs/setup-guide.md) as JSON files.

## Supported Backends

| Backend | Flag | Default URL |
|---|---|---|
| [Ollama](https://ollama.com/) | `--backend ollama` | `localhost:11434` |
| [LM Studio](https://lmstudio.ai/) | `--backend lmstudio` | `localhost:1234` |
| [oMLX](https://github.com/jundot/omlx) | `--backend openai --backend-label omlx` | `localhost:8000` |
| [llama-server](https://github.com/ggml-org/llama.cpp) | `--backend llama-server` | `localhost:8090` |
| [MiniMax](https://platform.minimax.io/) | `--backend minimax` | `api.minimax.io` |
| Any OpenAI-compatible | `--backend openai` | `localhost:8080` |

Override with `--base-url`. Use `--backend-label` to customize the name in result paths.

## Contribute Your Results

One data point is an anecdote. A table full of hardware is useful.

```bash
# 1. Fork and clone
git clone https://github.com/<you>/local-llm-bench && cd local-llm-bench

# 2. Run (auto-detects your hardware)
python3 bench.py --model llama3.1:8b

# 3. Commit and PR
git checkout -b results/my-hardware
git add results/
git commit -m "results: my hardware"
git push -u origin HEAD
gh pr create --title "results: my hardware" --body "Benchmark results"
```

Filenames encode your hardware specs, so there are no merge conflicts between contributors.

## Tuning

The benchmark auto-detects Ollama flags and includes them in result filenames.

**Ollama:** `OLLAMA_FLASH_ATTENTION=1` (faster prefill) | `OLLAMA_KV_CACHE_TYPE=q4_0` (4x smaller KV cache) | `iogpu.wired_limit_mb=8192` (more GPU memory). Restart Ollama after changes.

**LM Studio MLX:** Default prefill chunk size is 512. [Raising to 4096 nearly doubles prefill speed.](https://github.com/thornad/lmstudio-mlx-patch)

**All backends:** See the **[Setup Guide](docs/setup-guide.md)** for context window configuration, Qwen3.5 thinking mode, and step-by-step verification.

## License

MIT
