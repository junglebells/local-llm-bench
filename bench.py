#!/usr/bin/env python3
"""
LLM inference benchmark for local models.

WHAT THIS DOES:
  Runs a multi-turn conversation scenario against a local LLM backend and
  measures two things per turn:
    1. TTFT (Time To First Token) — how long before the first word appears
    2. Generation speed — how fast the response streams out

  Most LLM UIs only show generation speed (tok/s). This benchmark shows
  that TTFT often dominates total response time, especially as conversation
  context grows. See docs/paper.md for the full analysis.

HOW IT WORKS:
  1. Loads a scenario JSON file (e.g. scenarios/agent.json) that defines
     a system prompt and a sequence of conversation turns with tool calls.
  2. For each turn, sends the accumulated message history to the model
     and streams the response, measuring TTFT and generation time.
  3. Appends the model's response to the history for the next turn,
     so context grows naturally — just like a real conversation.
  4. Saves all metrics to a JSON file for later comparison.

USAGE:
  # Run against Ollama (default backend)
  python3 bench.py --model qwen3.5:35b-a3b --label "Ollama GGUF"

  # Run against LM Studio
  python3 bench.py --backend lmstudio --model mlx-community/qwen3.5-35b-a3b --label "LM Studio MLX"

  # Run against raw llama-server (llama.cpp without Ollama wrapper)
  python3 bench.py --backend llama-server --base-url http://localhost:8090 --model qwen3.5:35b-a3b --label "llama-server"

  # Run twice to compare cold vs warm cache
  python3 bench.py --model qwen3.5:35b-a3b --label "Ollama" --runs 2

  # Compare results from multiple runs
  python3 compare.py results/agent_ollama_gguf.json results/agent_lmstudio_mlx.json

REQUIREMENTS:
  - Python 3.8+ (stdlib only, no pip install needed)
  - A running inference backend (Ollama, LM Studio, or llama-server)
  - The model loaded in that backend
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

# Add the repo root to the import path so we can import from lib/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.backends import get_backend, get_model_info, DEFAULT_URLS
from lib.output import save_results, print_turn_header, print_turn_row, print_summary


# ── Install instructions shown when a backend isn't reachable ────────
# These help messages tell the user exactly what to do to fix the problem.
INSTALL_HINTS = {
    "ollama": (
        "Ollama is not running at {url}.\n"
        "\n"
        "  To fix:\n"
        "    1. Install:  brew install ollama\n"
        "    2. Start:    brew services start ollama\n"
        "    3. Pull:     ollama pull {model}\n"
        "    4. Verify:   curl {url}/api/tags\n"
        "\n"
        "  Or use --base-url to point to a different Ollama instance."
    ),
    "lmstudio": (
        "LM Studio is not running at {url}.\n"
        "\n"
        "  To fix:\n"
        "    1. Download LM Studio from https://lmstudio.ai/\n"
        "    2. Open it and load a model\n"
        "    3. Start the local server (Developer tab → Start Server)\n"
        "    4. Verify:   curl {url}/v1/models\n"
        "\n"
        "  Or use --base-url to point to a different LM Studio instance."
    ),
    "llama-server": (
        "llama-server is not running at {url}.\n"
        "\n"
        "  To fix:\n"
        "    1. Build llama.cpp: https://github.com/ggml-org/llama.cpp\n"
        "    2. Start:   ./llama-server -m model.gguf --port 8090\n"
        "    3. Verify:  curl {url}/v1/models\n"
        "\n"
        "  Or use --base-url to point to a different llama-server instance."
    ),
}


def check_backend(backend, base_url, model):
    """
    Verify that the inference backend is reachable before starting the benchmark.

    This prevents the confusing experience of watching 8 turns all fail with
    'Connection refused'. Instead, we fail fast with a clear message explaining
    what's wrong and how to fix it.
    """
    # Pick the right health-check URL for each backend
    if backend == "ollama":
        check_url = f"{base_url}/api/tags"
    else:
        check_url = f"{base_url}/v1/models"

    try:
        resp = urllib.request.urlopen(check_url, timeout=5)
        resp.read()
    except (urllib.error.URLError, OSError) as e:
        hint = INSTALL_HINTS[backend].format(url=base_url, model=model)
        print(f"Error: {hint}", file=sys.stderr)
        sys.exit(1)


def warm_up(stream_fn, base_url, model, backend):
    """
    Send a short throwaway request to ensure the model is loaded into memory.

    WHY THIS MATTERS:
      Ollama (and some other backends) load models on demand and unload them
      after an idle timeout (default: 5 minutes). If the model isn't loaded,
      Turn 1 TTFT includes model loading time (10-20s for a 35B model) which
      has nothing to do with prefill speed.

      By sending a trivial "hi" message first, we force the model into memory
      so Turn 1 measures actual prefill performance. The warm-up response is
      discarded — it's not part of the benchmark.

      Use --cold to skip this and include model loading time in the results.
    """
    print("  Warming up (loading model into memory)...", end="", flush=True)
    try:
        t_start = time.time()
        messages = [{"role": "user", "content": "hi"}]
        stream_fn(base_url, model, messages, max_tokens=1, temperature=0)
        warm_up_time = time.time() - t_start
        print(f" ready ({warm_up_time:.1f}s).\n")
        return round(warm_up_time, 3)
    except Exception as e:
        print(f" failed: {e}", file=sys.stderr)
        print(f"  Check that '{model}' is available in {backend}.", file=sys.stderr)
        sys.exit(1)


def load_scenario(path):
    """
    Load a scenario from a JSON file.

    A scenario defines:
    - system_prompt: the system message sent with every request
    - turns: a list of conversation turns, each with:
      - user: the user's message
      - tool: (optional) which tool the assistant calls
      - tool_result: (optional) the tool's output (JSON or text)
    - max_tokens: output token limit per turn
    - temperature: sampling temperature

    See scenarios/agent.json for an example.
    """
    if not os.path.exists(path):
        # List available scenarios to help the user pick one
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scenario_dir = os.path.join(script_dir, "scenarios")
        available = []
        if os.path.isdir(scenario_dir):
            available = [f for f in os.listdir(scenario_dir) if f.endswith(".json")]
        msg = f"Error: Scenario file not found: {path}\n"
        if available:
            msg += f"\n  Available scenarios in scenarios/:\n"
            for s in sorted(available):
                msg += f"    - {s}\n"
            msg += f"\n  Usage: python3 bench.py --scenario scenarios/{available[0]} --model MODEL --label LABEL"
        print(msg, file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in scenario file {path}: {e}", file=sys.stderr)
            sys.exit(1)


def run_scenario(scenario, stream_fn, base_url, model, runs=1, backend="ollama"):
    """
    Run a benchmark scenario and collect metrics per turn.

    TWO MODES (set via "mode" in the scenario JSON):

      "conversation" (default):
        Messages accumulate across turns, just like a real chat.
        Context grows with every turn, revealing the prefill bottleneck.

        Turn 1: [system, user1, tool_call, tool_result] → model responds
        Turn 2: [system, user1, ..., assistant1, user2, ...] → model responds

      "single-shot":
        Each turn starts fresh with only the system prompt.
        Context stays roughly constant. Tests raw prefill + generation
        without context accumulation — useful for classification, summary,
        and other stateless tasks.

        Turn 1: [system, user1] → model responds
        Turn 2: [system, user2] → model responds  (Turn 1 is gone)

    CONTEXT ESTIMATION:
      We estimate token count as character_count / 4. This is rough but
      consistent across runs, making relative comparisons valid.
    """
    all_results = []
    mode = scenario.get("mode", "conversation")

    for run in range(1, runs + 1):
        # Start each run with a fresh message history
        system_msg = {"role": "system", "content": scenario["system_prompt"]}
        messages = [system_msg]
        results = []
        max_tokens = scenario.get("max_tokens", 500)
        temperature = scenario.get("temperature", 0.6)

        # Print run header
        mode_label = "single-shot" if mode == "single-shot" else "conversation"
        print(f"\n{'='*85}")
        print(f"  {scenario['name'].upper()} BENCHMARK — {model} — Run {run}")
        print(f"  Backend: {backend} @ {base_url}")
        print(f"  {len(scenario['turns'])} turns, max_tokens={max_tokens}, mode={mode_label}")
        print(f"{'='*85}\n")
        print_turn_header(backend)

        # Track previous context size to calculate "new tokens" per turn
        prev_ctx_chars = len(scenario["system_prompt"])

        for i, turn in enumerate(scenario["turns"]):
            # ── In single-shot mode, reset to just the system prompt ──
            # Each turn is independent — no conversation history carried over.
            if mode == "single-shot":
                messages = [system_msg]
                prev_ctx_chars = len(scenario["system_prompt"])

            # ── Build messages for this turn ──────────────────────────
            # 1. Add the user's question
            messages.append({"role": "user", "content": turn["user"]})

            # 2. If there's a tool call, add the assistant's tool invocation
            #    and the tool's result as messages. This simulates the
            #    assistant-calls-tool pattern common in agent applications.
            tool = turn.get("tool")
            if tool:
                messages.append({"role": "assistant", "content": f"Let me run `{tool}` for you."})
                messages.append({"role": "user", "content": f"Tool `{tool}` returned:\n\n{turn['tool_result']}"})

            # ── Calculate context metrics ─────────────────────────────
            # How many tokens are in the full message history?
            ctx_chars = sum(len(m["content"]) for m in messages)
            ctx_tokens_est = ctx_chars // 4       # Rough estimate: 1 token ≈ 4 chars
            new_tokens_est = (ctx_chars - prev_ctx_chars) // 4  # New tokens added this turn

            try:
                # ── Send to model and measure ─────────────────────────
                # The stream function handles the HTTP request, streams
                # the response, and returns timing metrics.
                metrics = stream_fn(
                    base_url, model, messages,
                    max_tokens=max_tokens, temperature=temperature,
                )

                # ── Append model response to history ──────────────────
                # The model's response becomes part of the context for
                # the next turn. This is why context grows every turn.
                messages.append({"role": "assistant", "content": metrics["response"]})
                prev_ctx_chars = sum(len(m["content"]) for m in messages)

                # ── Build result record ───────────────────────────────
                result = {
                    "turn": i + 1,
                    "run": run,
                    "ctx_tokens_est": ctx_tokens_est,
                    "new_tokens_est": new_tokens_est,
                    "ttft": round(metrics["ttft"], 3),
                    "gen_time": round(metrics["gen_time"], 3),
                    "gen_tps": round(metrics["gen_tps"], 1),
                    "total": round(metrics["total"], 3),
                    "output_tokens": metrics["output_tokens"],
                }
                if tool:
                    result["tool"] = tool
                # Include Ollama-specific eval stats if available
                if metrics.get("prompt_eval_count") is not None:
                    result["prompt_eval_count"] = metrics["prompt_eval_count"]
                if metrics.get("prompt_eval_duration_ms"):
                    result["prompt_eval_duration_ms"] = round(metrics["prompt_eval_duration_ms"], 1)

                print_turn_row(result, backend)
                results.append(result)

            except Exception as e:
                # Record errors but keep going — one failed turn shouldn't
                # abort the whole benchmark
                print(f"{i+1:>4}  ERROR: {e}")
                messages.append({"role": "assistant", "content": "Error processing request."})
                prev_ctx_chars = sum(len(m["content"]) for m in messages)
                results.append({"turn": i + 1, "run": run, "error": str(e)})

        # Print run summary
        print()
        print_summary(results, f"Run {run}:")
        all_results.extend(results)

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="LLM inference benchmark — measures TTFT + generation speed per turn"
    )
    parser.add_argument("--scenario", default="scenarios/ops-agent.json",
                        help="Scenario JSON file (default: scenarios/ops-agent.json)")
    parser.add_argument("--backend", choices=["ollama", "lmstudio", "llama-server"],
                        default="ollama", help="Inference backend (default: ollama)")
    parser.add_argument("--base-url", default=None,
                        help="Override backend URL (default: auto from backend)")
    parser.add_argument("--model", required=True,
                        help="Model name/identifier as known by the backend")
    parser.add_argument("--label", required=True,
                        help="Human-readable label for this run (used in output and comparisons)")
    parser.add_argument("--runs", type=int, default=1,
                        help="Consecutive runs (default: 1). Use 2+ to test warm cache vs cold.")
    parser.add_argument("--cold", action="store_true",
                        help="Skip warm-up request (include model loading time in Turn 1)")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: results/<scenario>/<label>.json)")
    args = parser.parse_args()

    # Resolve backend URL (use default if not specified)
    base_url = args.base_url or DEFAULT_URLS[args.backend]

    # Get the appropriate streaming function for this backend
    stream_fn = get_backend(args.backend)

    # Load scenario data (resolve path relative to this script's directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = args.scenario if os.path.isabs(args.scenario) else os.path.join(script_dir, args.scenario)
    scenario = load_scenario(scenario_path)

    # ── Pre-flight check ─────────────────────────────────────────────
    # Verify the backend is reachable before starting. This catches
    # "service not running" early instead of failing on every turn.
    check_backend(args.backend, base_url, args.model)

    # ── Warm up ──────────────────────────────────────────────────────
    # By default, send a throwaway request to load the model into memory.
    # This ensures Turn 1 TTFT measures prefill, not model loading.
    # Use --cold to skip this and include model loading time.
    warm_up_time = None
    if not args.cold:
        warm_up_time = warm_up(stream_fn, base_url, args.model, args.backend)

    # Run the benchmark
    results = run_scenario(
        scenario, stream_fn, base_url, args.model,
        runs=args.runs, backend=args.backend,
    )

    # ── Check for valid results ────────────────────────────────────────
    # Don't save a junk file if every single turn failed — something is
    # fundamentally wrong (model not loaded, wrong model name, etc.)
    valid = [r for r in results if "error" not in r]
    if not valid:
        print(f"\nError: All {len(results)} turns failed. No results saved.", file=sys.stderr)
        print(f"  Check that '{args.model}' is loaded in {args.backend}.", file=sys.stderr)
        sys.exit(1)

    # Save results with metadata envelope
    # Results go into results/<scenario>/<label>.json so each scenario
    # gets its own directory. compare.py results/ops-agent/*.json works naturally.
    label_slug = args.label.lower().replace(" ", "_")
    outpath = args.output or os.path.join(script_dir, f"results/{scenario['name']}/{label_slug}.json")
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    meta = {
        "scenario": scenario["name"],
        "mode": scenario.get("mode", "conversation"),
        "label": args.label,
        "backend": args.backend,
        "model_info": get_model_info(args.backend, base_url, args.model),
        "runs": args.runs,
        "max_tokens": scenario.get("max_tokens", 500),
        "cold": args.cold,
    }
    if warm_up_time is not None:
        meta["warm_up_time"] = warm_up_time
    save_results(outpath, meta, results)
    print(f"\nResults saved to {outpath}")


if __name__ == "__main__":
    main()
