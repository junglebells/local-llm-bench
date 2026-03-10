# Part 2: Prompt Caching and Raw Engine Performance

Follow-up to the MLX vs GGUF benchmark. Same hardware, same conversation, new questions.

## The gap in Part 1

Part 1 measured MLX vs GGUF through LM Studio. Both engines re-processed the full conversation history on every turn — no prompt caching. TTFT grew linearly with context, from ~3s to ~19s (MLX) and ~3s to ~11s (GGUF).

But in real usage, inference servers cache the KV state from previous requests. When you send turn 5, the server already has turns 1-4 in its KV cache. It only needs to process the new tokens (your latest message + tool result). TTFT should stay roughly constant instead of growing with every turn.

Part 1 may have been measuring a worst case that nobody actually experiences.

## Hypotheses

### H1: Prompt caching makes TTFT roughly constant across turns

With caching, each turn only prefills the NEW tokens (~200-500 for a user message + tool result), not the full accumulated context. TTFT should plateau around 2-3s instead of climbing to 11-19s.

**If true:** Total response time becomes dominated by generation speed, which reverses the Part 1 conclusion. MLX's 53 tok/s generation advantage would matter again.

### H2: Caching could flip the MLX vs GGUF result

If caching eliminates most prefill time, the remaining total response time is:

```
total = small_constant_prefill + (output_tokens / generation_speed)
```

At 300 output tokens:
- MLX: ~2s prefill + 5.7s generation = ~7.7s
- GGUF: ~2s prefill + 10.7s generation = ~12.7s

MLX would win every turn, not just turn 1. The Part 1 conclusion would invert.

**But this assumes caching works equally well for both engines.** If MLX's cache is buggier or less effective (LM Studio has reported KV cache issues), the gap might persist.

### H3: Raw llama.cpp is faster than Ollama

Ollama wraps llama.cpp in a Go server layer. There's overhead for request routing, model management, and response formatting. Running llama-server directly should be faster, but by how much?

**Estimate:** 5-15% faster TTFT, negligible difference in generation speed.

### H4: LM Studio was not caching effectively in Part 1

Evidence: TTFT grew linearly in our Part 1 data (3.3s to 19.4s for MLX, 2.6s to 11.4s for GGUF). If caching were working, TTFT should have plateaued. Either LM Studio 0.4.5 doesn't cache between API requests, or the caching was not effective for our streaming multi-turn pattern.

## Test matrix

| Test | Engine | Port | Cache | What it answers |
|------|--------|------|-------|----------------|
| A | Ollama | 11434 | Automatic | Does Ollama's built-in KV cache flatten TTFT? |
| B | llama-server (raw) | 8090 | --cache-prompt | Raw llama.cpp baseline without Ollama overhead |
| C | LM Studio (GGUF) | 1234 | Default | Was Part 1 caching or not? (re-run for comparison) |

All tests use the same qwen3.5:35b-a3b model (GGUF Q4_K_M), same 8-turn agent conversation from Part 1.

MLX is excluded from Part 2 — the question here is about caching behavior and wrapper overhead, not the engine comparison. If caching changes the picture, we add MLX back in Part 3.

## What we measure

### Per-turn metrics (all backends)

| Metric | How | Why |
|--------|-----|-----|
| TTFT | Wall clock: request sent to first streamed token | Primary metric — does caching flatten this? |
| Generation time | Wall clock: first token to last token | Should be constant, sanity check |
| Generation tok/s | output_tokens / generation_time | Should match Part 1 |
| Total time | TTFT + generation time | What the user experiences |
| Output tokens | Count streamed content chunks | Normalize comparisons |

### Cache-specific metrics

| Backend | Cache indicator | How to read it |
|---------|----------------|----------------|
| Ollama | `prompt_eval_count` in `/api/chat` response | Absent = full cache hit. Present = tokens that needed processing |
| Ollama | `prompt_eval_duration` | Drops from seconds to microseconds on cache hit |
| llama-server | `tokens_cached` in response | Number of tokens reused from cache |
| llama-server | `/slots` endpoint | Per-slot cache state, `n_ctx`, prompt content |
| llama-server | `/metrics` (Prometheus) | `kv_cache_usage_ratio`, `kv_cache_tokens` |

## Conversation data

Same 8 turns from Part 1 (already defined in `bench_agent.py`):

| Turn | User message | Tool | New tokens (est.) |
|------|-------------|------|------------------|
| 1 | "Something feels off..." | server_status | ~576 (system + first exchange) |
| 2 | "Immich ML is eating CPU..." | service_logs | ~500 (user msg + log lines) |
| 3 | "Is it going to be OK memory-wise?" | docker_exec | ~200 (user msg + JSON) |
| 4 | "Check if last night's backup ran..." | backup_status | ~400 (user msg + JSON) |
| 5 | "Vault didn't eject again..." | disk_usage | ~500 (user msg + JSON) |
| 6 | "Time Machine at 75%..." | service_logs | ~500 (user msg + log lines) |
| 7 | "How big is the Matrix database?" | docker_exec | ~200 (user msg + text) |
| 8 | "2.1GB for Matrix seems like a lot..." | docker_exec | ~200 (user msg + JSON) |

With caching, only the "New tokens" column matters for TTFT. The accumulated context from previous turns is cached.

## Expected results

### If H1 is true (caching flattens TTFT)

| Turn | Context | Part 1 GGUF TTFT | Expected cached TTFT |
|------|---------|-------------------|---------------------|
| 1 | ~576 | 2.6s | 2.6s (cold, no cache) |
| 2 | ~1,100 | 3.6s | ~1.5s (only ~500 new tokens) |
| 3 | ~1,500 | 4.5s | ~1.0s (only ~200 new tokens) |
| 4 | ~2,000 | 5.9s | ~1.2s (only ~400 new tokens) |
| 5 | ~2,500 | 7.4s | ~1.5s (only ~500 new tokens) |
| 6 | ~3,100 | 9.1s | ~1.5s (only ~500 new tokens) |
| 7 | ~3,500 | 10.0s | ~1.0s (only ~200 new tokens) |
| 8 | ~4,000 | 11.4s | ~1.0s (only ~200 new tokens) |

Cumulative TTFT: Part 1 = 56.5s. Expected with cache = ~11.3s. A **5x reduction** in total wait time.

### If H2 is true (caching flips MLX vs GGUF)

With cached TTFT around 1-2s for both engines, total response time becomes:
- MLX: ~1.5s + 5.5s gen = ~7s per turn
- GGUF: ~1.5s + 9.5s gen = ~11s per turn

MLX would win every turn. The Part 1 conclusion inverts.

**This would mean our Part 1 finding, while technically correct, describes a scenario (no caching) that users rarely encounter in practice.** That's an important nuance to add to the article.

### If caching doesn't work as expected

TTFT still grows linearly. Possible reasons:
- Backend doesn't cache between separate HTTP requests
- Cache is invalidated by response tokens (the assistant's reply from turn N changes the prefix for turn N+1 unpredictably)
- Cache slot is too small to hold the full context

This is also a finding worth publishing.

## Setup

### Ollama (Test A)

Already running as a brew service. Model will be available after pull completes.

```bash
# Verify model loaded
ollama ps

# Run benchmark
python3 docs/benchmark/bench_agent_v2.py \
  --backend ollama \
  --base-url http://localhost:11434 \
  --model qwen3.5:35b-a3b \
  --label "Ollama"
```

### llama-server (Test B)

```bash
# Install
brew install llama.cpp

# Find the model file (Ollama stores GGUF blobs)
GGUF_PATH=$(ollama show qwen3.5:35b-a3b --modelfile 2>/dev/null | grep '^FROM ' | awk '{print $2}')

# Start server with caching enabled
llama-server \
  -m "$GGUF_PATH" \
  -ngl 99 \
  -c 8192 \
  --cache-prompt \
  --metrics \
  --slots \
  --host 127.0.0.1 \
  --port 8090

# Run benchmark
python3 docs/benchmark/bench_agent_v2.py \
  --backend llama-server \
  --base-url http://localhost:8090 \
  --model qwen3.5:35b-a3b \
  --label "llama-server"
```

### LM Studio re-run (Test C)

Load qwen3.5-35b-a3b GGUF in LM Studio, run same benchmark against port 1234.

```bash
python3 docs/benchmark/bench_agent_v2.py \
  --backend lmstudio \
  --base-url http://localhost:1234 \
  --model qwen/qwen3.5-35b-a3b \
  --label "LM Studio GGUF"
```

## Script requirements (bench_agent_v2.py)

Based on `bench_agent.py` from Part 1, with additions:

1. **Configurable backend URL** via `--base-url` (default: http://localhost:11434)
2. **Backend type** via `--backend` (ollama, llama-server, lmstudio) — controls which cache metrics to collect
3. **Ollama native API** for cache metrics: after each streamed response, query `/api/chat` stats or parse `prompt_eval_count` / `prompt_eval_duration` from the non-streaming response
4. **llama-server cache metrics**: parse `tokens_cached` from response, query `/slots` between turns
5. **Same turn data** as Part 1 (imported from shared module or inlined)
6. **Output JSON** with per-turn: ttft, gen_time, gen_tps, total, output_tokens, cache_tokens_reused, prompt_tokens_evaluated
7. **Two-pass option**: `--runs 2` to run the conversation twice (second run has turn 1 fully cached too)

## File plan

```
docs/benchmark/
  bench_agent_v2.py          # Part 2 benchmark script
  part2-design.md            # This file
  part2-results.md           # Results + analysis (after running)
```

Blog article update: add a "Part 2: Does prompt caching change the picture?" section to the famstack.dev guide.
