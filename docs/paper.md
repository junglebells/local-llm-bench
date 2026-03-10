# Why the "Faster" Model Is Actually Slower: MLX vs llama.cpp on Apple Silicon

*Benchmarked on a Mac Studio M1 Max (64 GB) running LM Studio 0.4.5 with Qwen3.5-35B-A3B at 4-bit quantization. March 2026.*

## Abstract

When running local LLMs on Apple Silicon, MLX models report nearly twice the generation speed of their GGUF/llama.cpp counterparts. This benchmark demonstrates that **generation speed (tok/s) is a misleading metric for real-world performance**. By separating prefill time (time-to-first-token) from generation time and simulating realistic multi-turn conversations with tool calls, we show that the "slower" GGUF model delivers faster total response times in most practical scenarios.

## 1. Introduction

Apple Silicon's unified memory architecture makes it uniquely suited for running large language models locally. Two inference engines dominate this space:

- **MLX** — Apple's native ML framework, optimized for Metal GPU. Uses SafeTensors format.
- **llama.cpp** — Georgi Gerganov's C++ inference engine. Uses GGUF format. Supports Metal acceleration.

Community benchmarks and UI-reported metrics consistently show MLX achieving higher tokens-per-second rates. This has led to a widespread recommendation: "On Apple Silicon, use MLX, not llama.cpp." ([Hacker News](https://news.ycombinator.com/item?id=43317924))

We challenge this advice by measuring what users actually experience: **total time from sending a message to receiving the complete response**.

## 2. The Two Models

Both models are the same architecture (Qwen3.5-35B-A3B) at the same quantization level (4-bit), differing only in format and inference engine.

| Property | MLX 4-bit | GGUF Q4_K_M |
|---|---|---|
| Source | mlx-community/Qwen3.5-35B-A3B-4bit | lmstudio-community/Qwen3.5-35B-A3B-GGUF |
| Engine | MLX v1.3.0 | llama.cpp v2.4.0 |
| Size in memory | 19.0 GB | 20.6 GB |
| Format | SafeTensors | GGUF |
| Quantization | 4-bit affine (group_size=64) | Q4_K_M |

## 3. Methodology

### 3.1 What We Measure

Every LLM request has two phases:

1. **Prefill** — The engine processes the entire input prompt (system message + conversation history + user message). This is done as a batch operation. The user experiences this as the delay before the first token appears, known as **Time To First Token (TTFT)**.

2. **Generation** — The engine produces the response one token at a time. Each new token requires attending to the full KV cache. The speed is measured in **tokens per second (tok/s)**.

Most benchmarks report only generation tok/s. We measure both phases independently using streaming mode: TTFT is the wall-clock time from request to first streamed token; generation time is from first token to last.

### 3.2 Test Environment

- **Hardware:** Mac Studio M1 Max, 64 GB unified memory
- **OS:** macOS 26.2 (Darwin 25.2.0)
- **Inference server:** LM Studio 0.4.5
- **Engines:** mlx-llm-mac-arm64-apple-metal-advsimd@1.3.0, llama.cpp-mac-arm64-apple-metal-advsimd@2.4.0
- **Model settings:** temperature=0.6, top_p=0.95, max_tokens=300, thinking mode disabled
- **Context length:** 50,000 tokens (default)

### 3.3 Benchmark Scripts

All scripts are available in `docs/benchmark/`:

| Script | Purpose |
|---|---|
| `bench_prefill_vs_gen.py` | Isolated prefill vs generation at fixed context sizes (36, 2.5K, 10K tokens) |
| `bench_conversation.py` | Simple multi-turn conversation with growing context |
| `bench_agent.py` | Realistic agent conversation with tool calls and JSON/log payloads |

## 4. Results

### 4.1 Isolated Benchmark — Prefill vs Generation

Fixed context sizes, single request per test.

#### Prefill Speed (Time To First Token)

| Context | MLX TTFT | GGUF TTFT | GGUF advantage |
|---|---|---|---|
| 36 tokens | 2.86s | 1.05s | **2.7x faster** |
| 2,500 tokens | 11.66s | 5.46s | **2.1x faster** |
| 10,000 tokens | 33.22s | 23.13s | **1.4x faster** |

GGUF/llama.cpp is faster at prefill at every context size tested.

#### Generation Speed

| | MLX | GGUF | MLX advantage |
|---|---|---|---|
| Generation | **53 tok/s** | 28 tok/s | **1.9x faster** |

Generation speed is consistent regardless of context size for both engines.

#### Total Response Time

| Context | Reply tokens | MLX total | GGUF total | Faster |
|---|---|---|---|---|
| 36 tokens | ~300 | **8.0s** | 11.8s | MLX |
| 2,500 tokens | ~120 | 14.1s | **9.2s** | GGUF |
| 10,000 tokens | ~70 | 34.5s | **25.7s** | GGUF |

**Observation:** MLX wins only when prefill is trivial and generation dominates. Once context exceeds ~1,500 tokens, GGUF's prefill advantage overcomes MLX's generation advantage.

### 4.2 Agent Conversation Benchmark

This is the core benchmark. It simulates a realistic 8-turn conversation between a user and an AI operations assistant managing a family home server. Each turn includes:

1. A user message (short — natural language question)
2. A pre-scripted tool call (the assistant invoking a tool)
3. A pre-scripted tool result (realistic JSON or log output)
4. A model-generated response (the assistant analyzing the tool output)

Context grows organically with each turn as the full history accumulates — exactly as it does in real agent applications.

#### Test Scenario

System prompt: Server operations assistant with 5 tools (server_status, service_logs, docker_exec, disk_usage, backup_status).

| Turn | User message | Tool called | Result type |
|---|---|---|---|
| 1 | "Something feels off with the server. Can you check what's running?" | server_status | JSON: 12 services with CPU/memory stats |
| 2 | "Immich ML is eating a lot of CPU. What's it doing?" | service_logs | Log: 16 lines of ML processing output |
| 3 | "We uploaded vacation photos yesterday. Is it going to be OK memory-wise?" | docker_exec | JSON: container stats (memory, CPU, network) |
| 4 | "Check if last night's backup ran. I want to make sure the vacation photos are safe." | backup_status | JSON: 3 backup job entries with warnings |
| 5 | "The vault didn't eject again. How's disk space looking on all drives?" | disk_usage | JSON: 3 volumes + data directory breakdown |
| 6 | "Time Machine is at 75%. Also did Paperless process the school documents I scanned?" | service_logs | Log: 14 lines of OCR/classification output |
| 7 | "How big is the Matrix database? It's been chatty lately." | docker_exec | Text: database size + table breakdown |
| 8 | "2.1GB for Matrix seems like a lot. Can we see which rooms take the most space?" | docker_exec | JSON: 7 rooms with event counts |

#### Results — Side by Side

| Turn | Context (est.) | MLX TTFT | MLX Gen | MLX Total | GGUF TTFT | GGUF Gen | GGUF Total | Faster |
|------|---------------|----------|---------|-----------|-----------|----------|------------|--------|
| 1 | ~576 | 3.3s | 5.5s | **8.9s** | 2.6s | 7.7s | 10.3s | MLX |
| 2 | ~1,100 | 9.4s | 5.3s | 14.7s | 3.6s | 9.9s | **13.4s** | GGUF |
| 3 | ~1,500 | 10.2s | 4.8s | 15.1s | 4.5s | 9.5s | **14.0s** | GGUF |
| 4 | ~2,000 | 12.3s | 4.9s | 17.2s | 5.9s | 10.6s | **16.5s** | GGUF |
| 5 | ~2,500 | 14.4s | 5.3s | 19.7s | 7.4s | 10.6s | **18.0s** | GGUF |
| 6 | ~3,100 | 15.8s | 5.3s | 21.1s | 9.1s | 8.6s | **17.7s** | GGUF |
| 7 | ~3,500 | 16.9s | 5.6s | 22.5s | 10.0s | 9.3s | **19.2s** | GGUF |
| 8 | ~4,000 | 19.4s | 5.5s | 24.9s | 11.4s | 10.6s | **22.0s** | GGUF |

#### Key Observations

**1. GGUF wins 7 out of 8 turns.** MLX wins only turn 1, where context is minimal.

**2. The gap widens with context.** By turn 8, GGUF is 2.9 seconds faster (12% improvement), despite producing tokens at nearly half the speed.

**3. MLX prefill scales poorly.** MLX TTFT grows from 3.3s to 19.4s (5.9x increase for 7x context growth). GGUF TTFT grows from 2.6s to 11.4s (4.4x increase). The scaling ratio diverges.

**4. Generation speed is constant.** MLX stays at 53±2 tok/s and GGUF at 28±1 tok/s across all turns. Context size does not affect generation speed — only prefill.

**5. Prefill dominates total time.** By turn 8, prefill accounts for 78% of MLX's total time but only 52% of GGUF's. This is why MLX's generation advantage becomes irrelevant.

#### Cumulative Wait Time (Full Conversation)

| | MLX | GGUF |
|---|---|---|
| Sum of all TTFT (waiting before any response) | 101.8s | 56.5s |
| Sum of all generation time | 42.3s | 76.5s |
| **Total conversation time** | **144.1s** | **131.0s** |
| Time saved with GGUF | | **13.1s (9%)** |

Over an 8-turn agent conversation, the user waits **45 seconds longer for first tokens** with MLX. GGUF's slower generation only costs 34 seconds. Net: GGUF saves 13 seconds.

### 4.3 Effective Throughput

The "effective throughput" is what the user actually experiences: output tokens divided by total wall-clock time.

| Context | MLX effective | GGUF effective | Headline tok/s |
|---|---|---|---|
| 36 tokens | 34 tok/s | 25 tok/s | MLX: 53, GGUF: 28 |
| 2,500 tokens | 9 tok/s | 12 tok/s | MLX: 53, GGUF: 28 |
| 10,000 tokens | 2 tok/s | 3 tok/s | MLX: 53, GGUF: 28 |

The headline tok/s number stays constant. The effective throughput drops dramatically. This disconnect is the core of the misleading metric problem.

## 5. Analysis

### 5.1 Why MLX Prefill Is Slower

Both engines run on the same Metal GPU. The difference is in how they process prompt batches:

- **llama.cpp** has years of optimization for batch prompt processing on Metal — tuned compute shaders, efficient memory access patterns, KV cache quantization, and flash attention support. The project has been continuously optimized since December 2022.

- **MLX** is Apple's newer framework (released December 2023). Its per-token forward pass has lower overhead, making generation faster. But its batch processing pipeline for prefill appears less optimized for LLM-specific patterns.

### 5.2 When MLX Wins

MLX is the better choice when:
- **Prompts are short** (<1K tokens) and replies are long (creative writing, brainstorming)
- **Conversations start fresh** frequently rather than building long threads
- **Streaming UX matters** — at 53 tok/s, text flows noticeably faster on screen
- **Single-shot queries** — "translate this", "write a regex", "explain this error"

### 5.3 When GGUF Wins

GGUF/llama.cpp is the better choice when:
- **Agent/tool-calling workflows** — system prompts, tool definitions, and multi-step history create large contexts from the start
- **Chat conversations** — context accumulates naturally, crossing the ~1.5K threshold within a few turns
- **RAG applications** — retrieved document chunks inject 1K–10K tokens into every request
- **Bot integrations** (Matrix, Discord, Slack) — bots maintain conversation history per room
- **API backends** — total response latency matters more than streaming appearance

### 5.4 The Misleading Metric

Most LLM UIs (LM Studio, Open WebUI, Ollama) prominently display generation speed in tok/s. This number measures only one phase of inference and can paint an inverted picture of actual performance:

```
         Headline metric says:    MLX is 1.9x faster (53 vs 28 tok/s)
  Actual experience at 4K ctx:    GGUF is 1.1x faster (22.0s vs 24.9s total)
```

The discrepancy grows with context size. At 10K context, MLX shows 53 tok/s but the effective throughput is just 2 tok/s.

## 6. Limitations

- **Single model tested.** Results may differ for other architectures, particularly dense (non-MoE) models where prefill characteristics differ.
- **Single hardware configuration.** M1 Max with 64 GB. Results may vary on M2/M3/M4 chips, different RAM configurations, or when memory pressure is higher.
- **LM Studio-specific.** Both engines are invoked through LM Studio's wrappers. Running llama.cpp or MLX directly (via CLI or Python) may show different overhead characteristics.
- **Token estimates.** Context sizes are estimated from character count (÷4). Actual tokenization may differ.
- **No prompt caching.** Neither engine was configured with prompt caching, which could reduce prefill time for repeated conversation prefixes.

## 7. Conclusion

The tok/s metric that dominates LLM benchmarking discourse is fundamentally incomplete. It measures generation speed only, ignoring the prefill phase that becomes the primary bottleneck in any real-world application involving context — which is nearly all of them.

For the increasingly common agentic use case — AI assistants that call tools, maintain conversation history, and process structured data — llama.cpp/GGUF delivers better actual performance on Apple Silicon despite reporting half the generation speed.

**The right question is not "how fast does it generate?" but "how long do I wait for a complete response?"**

## 8. Reproducing These Results

### Requirements

- LM Studio 0.4.5+ with both MLX and llama.cpp engines installed
- Qwen3.5-35B-A3B in both formats:
  - `mlx-community/Qwen3.5-35B-A3B-4bit`
  - `lmstudio-community/Qwen3.5-35B-A3B-GGUF` (Q4_K_M)

### Running the Benchmarks

```bash
# Isolated prefill vs generation (load each model first with lms load)
python3 docs/benchmark/bench_prefill_vs_gen.py "mlx-community/qwen3.5-35b-a3b" "MLX"
python3 docs/benchmark/bench_prefill_vs_gen.py "qwen/qwen3.5-35b-a3b" "GGUF"

# Simple conversation with growing context
python3 docs/benchmark/bench_conversation.py "mlx-community/qwen3.5-35b-a3b" "MLX"
python3 docs/benchmark/bench_conversation.py "qwen/qwen3.5-35b-a3b" "GGUF"

# Agent conversation with tool calls (core benchmark)
python3 docs/benchmark/bench_agent.py "mlx-community/qwen3.5-35b-a3b" "MLX"
python3 docs/benchmark/bench_agent.py "qwen/qwen3.5-35b-a3b" "GGUF"
```

### Raw Results

JSON results are stored in `docs/benchmark/`:
- `results_agent_mlx.json`
- `results_agent_gguf.json`
- `results_conversation_mlx.json`

## References

- [Production-Grade Local LLM Inference on Apple Silicon: A Comparative Study](https://arxiv.org/abs/2511.05502) — Academic comparison of MLX, llama.cpp, Ollama, MLC-LLM, and PyTorch MPS
- [llama.cpp issue #19366: MLX 2.5x faster generation than llama.cpp](https://github.com/ggml-org/llama.cpp/issues/19366) — Documenting the generation speed gap
- [Hacker News: "use MLX, not llama.cpp"](https://news.ycombinator.com/item?id=43317924) — Community conventional wisdom
- [llama.cpp Apple Silicon performance tracking](https://github.com/ggml-org/llama.cpp/discussions/4167) — Ongoing performance discussion

---

*Benchmarked and written as part of the [famstack](https://famstack.dev) family server project — a home server stack running on Apple Silicon.*
