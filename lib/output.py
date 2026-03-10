"""
Result storage and display helpers.

RESULT FORMAT:
  All benchmark results are stored as JSON files with a standard envelope:

  {
      "meta": {
          "scenario": "agent",              # which scenario was run
          "label": "Ollama GGUF",           # human-readable run label
          "backend": "ollama",              # which backend adapter was used
          "model": "qwen3.5:35b-a3b",      # model identifier
          "base_url": "http://...",         # backend URL
          "runs": 1,                        # how many consecutive runs
          "max_tokens": 500,                # output token limit
          "timestamp": "2026-03-09T14:30",  # when the benchmark ran
          "hostname": "mac-merlin.local"    # which machine ran it
      },
      "results": [
          {
              "turn": 1,           # turn number within the conversation
              "run": 1,            # which run (for multi-run benchmarks)
              "ctx_tokens_est": 575,  # estimated total context tokens
              "new_tokens_est": 422,  # estimated NEW tokens this turn
              "ttft": 2.633,       # seconds waiting for first token
              "gen_time": 10.995,  # seconds of token generation
              "gen_tps": 18.8,     # generation tokens per second
              "total": 13.629,     # total wall clock time
              "output_tokens": 207 # tokens in the model's response
          },
          ...
      ]
  }

  The "meta" block is added automatically by save_results().
  The compare.py script reads these files and aligns results by turn number.
"""

import json
import platform
import subprocess
import time


def _sysctl(key):
    """Read a single sysctl value. Returns None on failure."""
    try:
        return subprocess.check_output(
            ["sysctl", "-n", key], stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_system_info():
    """
    Collect hardware and OS specs for the current machine.

    Designed for the community comparison use case — result files should be
    self-documenting and shareable without revealing personal information.

    WHAT WE COLLECT (and why):
      - chip: "Apple M1 Max" — the primary hardware identifier
      - gpu_cores: 24 — differentiates M1 Pro 14-core vs 16-core, etc.
                   This is the #1 factor for Metal inference performance.
      - cpu_cores: 10 — total CPU cores (affects prefill on some engines)
      - cpu_cores_performance: 8 — P-cores (fast cores)
      - cpu_cores_efficiency: 2 — E-cores (background cores)
      - memory_gb: 64 — unified memory size (determines max model size)
      - os_version: "26.2" — macOS version
      - arch: "arm64" — architecture

    WHAT WE DON'T COLLECT:
      - hostname — identifies the user
      - base_url — useless for comparison, could leak custom URLs
      - username, IP, serial number — obvious privacy concerns

    On macOS, we use sysctl (instant) for most values and system_profiler
    (~300ms) for GPU core count which sysctl doesn't expose.
    """
    info = {
        "os": platform.system(),
        "os_version": platform.mac_ver()[0] or platform.release(),
        "arch": platform.machine(),
    }

    if platform.system() == "Darwin":
        # Chip name (e.g. "Apple M1 Max")
        chip = _sysctl("machdep.cpu.brand_string")
        if chip:
            info["chip"] = chip

        # Total memory in bytes → GB
        mem = _sysctl("hw.memsize")
        if mem:
            try:
                info["memory_gb"] = int(mem) // (1024 ** 3)
            except ValueError:
                pass

        # CPU core counts — total, P-cores (fast), E-cores (efficiency)
        ncpu = _sysctl("hw.ncpu")
        if ncpu:
            try:
                info["cpu_cores"] = int(ncpu)
            except ValueError:
                pass

        p_cores = _sysctl("hw.perflevel0.logicalcpu")
        if p_cores:
            try:
                info["cpu_cores_performance"] = int(p_cores)
            except ValueError:
                pass

        e_cores = _sysctl("hw.perflevel1.logicalcpu")
        if e_cores:
            try:
                info["cpu_cores_efficiency"] = int(e_cores)
            except ValueError:
                pass

        # GPU core count — the #1 differentiator for Metal inference.
        # sysctl doesn't expose this, so we use system_profiler (~300ms).
        try:
            sp_output = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"],
                stderr=subprocess.DEVNULL,
            ).decode()
            for line in sp_output.splitlines():
                if "Total Number of Cores" in line:
                    gpu_cores = int(line.split(":")[-1].strip())
                    info["gpu_cores"] = gpu_cores
                    break
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            pass

    return info


def save_results(path, meta, results):
    """
    Save benchmark results with a metadata envelope.

    Automatically adds timestamp and system specs to the metadata so results
    are self-documenting and shareable. No personal information is included —
    no hostname, no IP, no username. See get_system_info() for what we collect.
    """
    envelope = {
        "meta": {
            **meta,
            "system": get_system_info(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "results": results,
    }
    with open(path, "w") as f:
        json.dump(envelope, f, indent=2)
    return path


def load_results(path):
    """
    Load benchmark results from a JSON file.

    Handles two formats:
    - Standard envelope: {"meta": {...}, "results": [...]}
    - Legacy bare array: [{turn: 1, ...}, ...]  (from early Part 1 scripts)

    Legacy arrays are wrapped in a minimal envelope so compare.py can
    handle them without special cases.
    """
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        # Legacy format — wrap in envelope with the filename as label
        return {"meta": {"label": path}, "results": data}
    return data


def print_turn_header(backend=None):
    """
    Print the column header for the turn-by-turn benchmark table.

    The header adapts based on backend — Ollama gets an extra "PrEval" column
    showing how many prompt tokens were evaluated (from llama.cpp internals).
    """
    h = f"{'Turn':>4}  {'Ctx':>8}  {'New':>6}  {'Prefill':>9}  {'Gen':>7}  {'Tok/s':>6}  {'Total':>7}  {'Out':>5}"
    if backend == "ollama":
        h += f"  {'PrEval':>7}"
    print(h)
    print("-" * len(h))


def print_turn_row(r, backend=None):
    """
    Print one row of the turn-by-turn benchmark table.

    Each row shows metrics for a single conversation turn:
    - Ctx: estimated total context tokens (all messages so far)
    - New: estimated NEW tokens added this turn (user msg + tool result)
    - TTFT: time to first token (prefill + network overhead)
    - Gen: generation time (first token to last token)
    - Tok/s: generation speed (output_tokens / gen_time)
    - Total: TTFT + Gen (what the user actually waits)
    - Out: how many tokens the model produced
    - PrEval: prompt tokens evaluated by llama.cpp (Ollama only)
    """
    row = (
        f"{r['turn']:>4}  {r.get('ctx_tokens_est', 0):>8,}  {r.get('new_tokens_est', 0):>6,}  "
        f"{r['ttft']:>8.2f}s  {r['gen_time']:>6.2f}s  "
        f"{r['gen_tps']:>5.1f}  {r['total']:>6.2f}s  "
        f"{r['output_tokens']:>5}"
    )
    if backend == "ollama":
        pe = r.get("prompt_eval_count")
        pe_str = str(pe) if pe is not None else "-"
        row += f"  {pe_str:>7}"
    print(row)


def print_summary(results, label=""):
    """
    Print aggregate stats for a benchmark run.

    Shows:
    - Total TTFT: cumulative time spent waiting for first tokens (staring at blank screen)
    - Total generation: cumulative time watching tokens stream
    - Total time: the full conversation wall clock
    - Avg gen tok/s: average generation speed across all turns
    """
    valid = [r for r in results if "error" not in r]
    if not valid:
        print("  No valid results.")
        return
    total_ttft = sum(r["ttft"] for r in valid)
    total_gen = sum(r["gen_time"] for r in valid)
    total_time = sum(r["total"] for r in valid)
    avg_tps = sum(r["gen_tps"] for r in valid) / len(valid)
    prefix = f"  {label} " if label else "  "
    print(f"{prefix}Total prefill:    {total_ttft:>7.1f}s")
    print(f"{prefix}Total generation: {total_gen:>7.1f}s")
    print(f"{prefix}Total time:       {total_time:>7.1f}s")
    print(f"{prefix}Avg gen tok/s:    {avg_tps:>7.1f}")
