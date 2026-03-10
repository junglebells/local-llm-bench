# local-llm-bench: Scenario-Based LLM Benchmark for Apple Silicon

- Compare engines, models, and quantizations across scenarios
- Measure how context size impacts performance
- See what you actually wait for, not just the tok/s counter

Works on any Apple Silicon Mac (M1 through M5, MacBook Air to Mac Studio).

## The Problem

LLM interfaces report generation speed: *"53 tok/s"*. That sounds fast. But every response starts with a **prefill phase** where the model processes your entire conversation history before producing the first token. As your conversation grows, prefill grows too, and nobody shows you that number.

In an 8-turn agent conversation, the model with 53 tok/s loses to the model with 28 tok/s because its prefill is 2x slower. **Generation speed alone is misleading.**

**Read the full analysis: [MLX vs llama.cpp on Apple Silicon](https://famstack.dev/guides/mlx-vs-gguf-apple-silicon)**

## What It Measures

```
[User sends message]
     |
     |  Prefill (Time To First Token)
     |  ← Model processes entire conversation history
     |  ← Grows with every turn (this is the hidden cost)
     v
[First token appears]
     |
     |  Generation (tok/s)
     |  ← Model produces output tokens
     |  ← Stays roughly constant
     v
[Response complete]
```

**Scenario types:**
- **Multi-turn conversations**: agent workflows, chat sessions, tool-calling chains. Context grows each turn, revealing prefill scaling behavior.
- **Single-shot tasks**: document conversion, classification, summarization. One large input, one output. Pure prefill-vs-generation comparison.

## Quick Start

### Requirements

- Python 3.8+ (stdlib only, no pip install needed)
- A running inference backend: [Ollama](https://ollama.com/), [LM Studio](https://lmstudio.ai/), or raw [llama-server](https://github.com/ggml-org/llama.cpp)
- A model loaded in that backend

### Run a Benchmark

```bash
# Against Ollama (default)
python3 bench.py --model qwen3.5:35b-a3b --label "Ollama GGUF"

# Against LM Studio (MLX model)
python3 bench.py --backend lmstudio \
  --model mlx-community/qwen3.5-35b-a3b --label "LM Studio MLX"

# Against LM Studio (GGUF model via llama.cpp)
python3 bench.py --backend lmstudio \
  --model lmstudio-community/qwen3.5-35b-a3b-gguf --label "LM Studio GGUF"

# Against raw llama-server (llama.cpp without Ollama)
python3 bench.py --backend llama-server --base-url http://localhost:8090 \
  --model qwen3.5:35b-a3b --label "llama-server"

# Include model loading time in the measurement
python3 bench.py --model qwen3.5:35b-a3b --label "Ollama cold" --cold
```

By default the benchmark warms up the model before starting, so Turn 1 measures actual prefill, not model loading. Use `--cold` to include loading time.

### Compare Results

```bash
python3 compare.py results/ops-agent/ollama_gguf.json results/ops-agent/lmstudio_mlx.json

# Or compare all runs for a scenario
python3 compare.py results/ops-agent/*.json
```

Example output:

```
==========================================================================================
  OPS-AGENT BENCHMARK COMPARISON
==========================================================================================

                     LM Studio GGUF     LM Studio MLX
                     ───────────────── ─────────────────
  Turn 1  Prefill             2.60s             3.33s
               Gen             7.71s             5.54s
             Total            10.31s             8.87s

  Turn 8  Prefill            11.38s            19.40s    ← prefill dominates
               Gen            10.63s             5.50s
             Total            22.02s            24.91s
──────────────────── ───────────────── ─────────────────
    Total Prefill             54.4s            101.8s
         Total Gen             76.8s             42.3s
        Total Time            131.2s            144.0s
     Avg Gen tok/s             28.2              54.2

  Winner (fastest total): LM Studio GGUF (131.2s)
  LM Studio MLX: +12.9s slower (9%)
```

## What You Can Compare

This benchmark helps answer questions like:

- **MLX vs llama.cpp (GGUF)**: Which inference engine is faster for your workload? MLX has higher tok/s but slower prefill. The crossover depends on context length.
- **Ollama vs raw llama-server**: How much overhead does Ollama add? Is its KV cache worth it?
- **Different models**: How does a 7B model compare to a 35B MoE model on your hardware? Where does memory bandwidth become the bottleneck?
- **Different quantizations**: Q4_K_M vs Q8_0 vs FP16. What's the real-world tradeoff?
- **Your Mac vs others**: Share your result JSON files and compare across machines. Mac Mini M2 vs MacBook Pro M3 vs Mac Studio M4. How much does the hardware matter?

## Supported Backends

| Backend | Flag | Default URL | Engine |
|---|---|---|---|
| Ollama | `--backend ollama` | `http://localhost:11434` | llama.cpp (GGUF) with KV cache, model management |
| LM Studio | `--backend lmstudio` | `http://localhost:1234` | MLX or llama.cpp depending on model format |
| llama-server | `--backend llama-server` | `http://localhost:8090` | Raw llama.cpp (GGUF), no wrapper overhead |

Override any URL with `--base-url`.

## Scenarios

Scenarios are JSON files that define what to benchmark. Each scenario has a system prompt and a sequence of turns that the benchmark replays against the model.

### Included Scenarios

| Scenario | Turns | Mode | Description |
|---|---|---|---|
| [ops-agent.json](scenarios/ops-agent.json) | 8 | conversation | Server ops agent with tool calls. JSON payloads, log analysis, growing context |
| [doc-summary.json](scenarios/doc-summary.json) | 5 | single-shot | Document classification. Short output from long input |
| [prefill-test.json](scenarios/prefill-test.json) | 4 | single-shot | Prefill scaling. Same short reply at 655, 1.5K, 3K, and 8.5K context |

### Creating Your Own

```json
{
  "name": "my-scenario",
  "description": "What this scenario tests",
  "system_prompt": "You are a helpful assistant.",
  "max_tokens": 500,
  "temperature": 0.6,
  "turns": [
    {
      "user": "Hello, how are you?"
    },
    {
      "user": "Can you check something for me?",
      "tool": "my_tool",
      "tool_result": "{ \"status\": \"ok\" }"
    }
  ]
}
```

Each turn has a `user` message. Optionally, `tool` and `tool_result` simulate the assistant calling a tool. This adds realistic context growth, just like agent frameworks do.

For single-shot benchmarks, create a scenario with one turn and a large user message (e.g., a document to summarize or classify).

## Result Format

Results are saved as JSON with a metadata envelope:

```json
{
  "meta": {
    "scenario": "ops-agent",
    "label": "Ollama GGUF",
    "backend": "ollama",
    "model": "qwen3.5:35b-a3b",
    "warm_up_time": 1.234,
    "timestamp": "2026-03-09T14:30:00",
    "hostname": "mac-merlin.local"
  },
  "results": [
    {
      "turn": 1,
      "ctx_tokens_est": 575,
      "ttft": 2.633,
      "gen_time": 10.995,
      "gen_tps": 18.8,
      "total": 13.629,
      "output_tokens": 207
    }
  ]
}
```

Results are grouped by scenario: `results/ops-agent/`, `results/doc-convert/`, etc. Share your JSON files to compare across machines.

## Project Structure

```
local-llm-bench/
├── bench.py              # Main benchmark runner
├── compare.py            # Side-by-side comparison tool
├── lib/
│   ├── backends.py       # Backend adapters (Ollama, LM Studio, llama-server)
│   └── output.py         # Result storage and display helpers
├── scenarios/
│   ├── ops-agent.json    # 8-turn server ops conversation with tool calls
│   ├── doc-summary.json  # 5-turn document classification
│   └── prefill-test.json # Prefill scaling at different context sizes
├── results/              # Saved benchmark results, grouped by scenario
│   ├── ops-agent/
│   ├── doc-summary/
│   └── prefill-test/
└── docs/
    ├── paper.md          # Full MLX vs GGUF analysis
    ├── part2-design.md   # Part 2 design (caching hypotheses)
    └── part2-findings.md # Part 2 results
```

All source files include detailed inline comments explaining what each section does and why. Designed to be readable by non-Python developers.

## Analysis & Findings

We used this benchmark to investigate MLX vs GGUF performance and Ollama's prompt caching on Apple Silicon. The full analysis with data and methodology is published at **[famstack.dev](https://famstack.dev)**.

Raw data and research notes are in [docs/](docs/).

## Hardware Tested

- Mac Studio M1 Max, 64GB unified memory

We'd love to see results from other Apple Silicon Macs. Run the benchmark, share your result files, and help build a picture of local LLM performance across the Mac lineup.

## License

MIT
