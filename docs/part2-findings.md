# Part 2 Findings — Prompt Caching and Ollama vs LM Studio

Tested 2026-03-09. Same hardware (Mac Studio M1 Max 64GB), same model (qwen3.5:35b-a3b Q4_K_M).

## Key Findings

### 1. Ollama KV caching works, but imperfectly

Caching is automatic in Ollama. In multi-turn conversations, the prefix from previous turns is reused. TTFT still grows with context, but 37% slower than without caching.

| Metric | LM Studio GGUF (no cache) | Ollama (with cache) |
|--------|--------------------------|---------------------|
| Total TTFT (8 turns) | 56.5s | 36.1s |
| TTFT growth pattern | Linear (2.6s to 11.4s) | Sublinear (2.6s to 7.6s) |

Cache does NOT make TTFT constant as hypothesized. There's per-request overhead that scales with total KV cache size even when the prefix is cached (likely attention index rebuilding).

### 2. `prompt_eval_count` is NOT a cache hit indicator

The Ollama API always reports total prompt tokens in `prompt_eval_count`, whether cached or not. The field is never absent on cache hit (contrary to some documentation).

The real cache indicators:
- **Wall time / TTFT drop** on repeated identical requests (11.5s → 0.47s)
- **`prompt_eval_duration` drop** (relative, not absolute)

### 3. Ollama generation is slower than LM Studio

Same model, same Q4_K_M quantization, different speed:

| Measurement | Ollama | LM Studio GGUF |
|-------------|--------|----------------|
| Internal gen speed (eval_duration) | 22 tok/s | ~28 tok/s |
| Observed streaming speed | 17-19 tok/s | ~28 tok/s |

Two overhead layers:
- llama.cpp build/config: 22 vs 28 tok/s (Ollama may use different compile flags or batch sizes)
- Streaming format: JSON-per-line adds ~15-20% overhead on top

`presence_penalty` (default 1.5 in model) has negligible effect (21.3 vs 22.1 tok/s).

### 4. Thinking mode complicates benchmarking

Qwen3.5 defaults to thinking enabled. The OpenAI-compatible `/v1/chat/completions` endpoint does NOT support `think: false`. Only the native `/api/chat` endpoint does. Without disabling thinking:
- Model spends tokens on `<think>` blocks invisible to the streaming parser
- Some turns produce 0 visible output tokens (entire budget consumed by thinking)
- TTFT measurement includes thinking time, not just prefill

For Ollama: `"think": false` in the native API works.
For Modelfile: `PARAMETER think false` does NOT work (unknown parameter).
For Kit bots via OpenAI endpoint: need a custom Modelfile with modified template or use native API.

### 5. Net result: Ollama is slower overall

| Metric | LM Studio GGUF | Ollama |
|--------|----------------|--------|
| Total TTFT | 56.5s | 36.1s |
| Total generation | 76.5s | 118.7s |
| **Total conversation** | **131.0s** | **154.8s** |

Caching saves 20s on prefill, but slower generation costs 42s. Net: 24s slower.

## Hypotheses Status

| # | Hypothesis | Status |
|---|-----------|--------|
| H1 | Caching makes TTFT constant | **Partially true** — TTFT grows slower but not constant |
| H2 | Caching flips MLX vs GGUF result | **Not tested yet** — need MLX with caching |
| H3 | Raw llama-server faster than Ollama | **Not tested yet** — would isolate Ollama overhead |
| H4 | LM Studio wasn't caching in Part 1 | **Likely true** — linear TTFT growth matches no-cache behavior |

## Open Questions

- Does LM Studio 0.4.5 cache between API requests? (Part 1 data suggests no)
- Can llama-server match LM Studio's 28 tok/s? Or is LM Studio faster?
- Does MLX in LM Studio cache? If so, how much does it help?
- What's the right `max_tokens` for realistic agent responses? (300 may be too low)

## Next Steps

- Run llama-server directly to isolate wrapper overhead
- Re-run with max_tokens: 500 for more realistic response lengths
- Test LM Studio with explicit cache verification
- Structure into standalone benchmark repo
