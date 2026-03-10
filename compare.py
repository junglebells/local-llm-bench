#!/usr/bin/env python3
"""
Compare results from multiple benchmark runs side by side.

WHAT THIS DOES:
  Takes two or more benchmark result files and prints a comparison table
  showing how each setup performed on every conversation turn. This is how
  you answer questions like "Is MLX faster than GGUF?" or "Does Ollama's
  cache actually help?"

HOW IT WORKS:
  1. Loads each result file (see lib/output.py for the file format).
  2. Groups results by scenario name — so if you mix "agent" and "coding"
     results, each scenario gets its own comparison section.
  3. For each scenario, prints a turn-by-turn comparison showing TTFT,
     generation time, and total time for each setup.
  4. Prints aggregate totals and declares a winner based on total time.

  Only Run 1 results are used for comparison (multi-run files include
  Run 2+ for cache testing, but apples-to-apples comparison needs the
  same run number from each setup).

OUTPUT FORMAT:
  The table is designed for terminal viewing. Example:

                        Ollama GGUF      LM Studio MLX
                       ─────────────────  ─────────────────
     Turn 1  TTFT           2.63s              1.15s
                Gen          10.99s              5.45s
              Total          13.63s              6.60s

     Turn 2  TTFT           4.03s              5.46s
                Gen          16.97s              8.49s
              Total          21.01s             13.95s
     ...

USAGE:
  # Compare two specific runs
  python3 compare.py results/agent_ollama_gguf.json results/agent_lmstudio_mlx.json

  # Compare everything in the results directory
  python3 compare.py results/*.json
"""

import argparse
import json
import os
import sys

from lib.output import load_results


def compare(files):
    """
    Load multiple result files and print a side-by-side comparison.

    Each file is a benchmark result in the standard envelope format
    (see lib/output.py). Files that don't exist are skipped with a warning.
    """
    runs = []
    for f in files:
        if not os.path.exists(f):
            print(f"Warning: {f} not found, skipping")
            continue
        runs.append(load_results(f))

    if not runs:
        print("No result files to compare.")
        return

    # ── Group by scenario ────────────────────────────────────────────
    # Different scenarios (e.g. "agent", "coding") get separate comparison
    # sections. This way you can pass `results/*.json` and each scenario
    # is compared within its own group.
    scenarios = {}
    for run in runs:
        scenario = run["meta"].get("scenario", "unknown")
        scenarios.setdefault(scenario, []).append(run)

    for scenario_name, scenario_runs in scenarios.items():
        print(f"\n{'='*90}")
        print(f"  {scenario_name.upper()} BENCHMARK COMPARISON")
        print(f"{'='*90}\n")

        # ── Build column headers ─────────────────────────────────────
        # Each result file becomes a column. The label comes from the
        # benchmark metadata (the --label flag when running bench.py).
        labels = [r["meta"].get("label", "?") for r in scenario_runs]
        col_width = max(18, max(len(l) for l in labels) + 2)

        # Print header row with labels
        print(f"{'':>20}", end="")
        for label in labels:
            print(f"{label:>{col_width}}", end="")
        print()
        # Print separator line under each label
        print(f"{'':>20}", end="")
        for _ in labels:
            print(f"{'─' * (col_width - 1):>{col_width}}", end="")
        print()

        # ── Determine how many turns to compare ─────────────────────
        # Use Run 1 only — Run 2+ exists for cache testing and shouldn't
        # be mixed into the primary comparison.
        max_turns = max(
            max((r["turn"] for r in run["results"] if r.get("run", 1) == 1), default=0)
            for run in scenario_runs
        )

        # ── Per-turn comparison ──────────────────────────────────────
        # For each turn, show three rows: TTFT, Gen time, and Total.
        # This lets you see WHERE each setup wins or loses.
        # Early turns (small context) → TTFT is small, Gen dominates.
        # Late turns (large context) → TTFT grows, may dominate Total.
        for turn_num in range(1, max_turns + 1):
            # Prefill row — time waiting for the first token (TTFT)
            print(f"{'Turn ' + str(turn_num) + '  Prefill':>20}", end="")
            for run in scenario_runs:
                r = next((r for r in run["results"] if r["turn"] == turn_num and r.get("run", 1) == 1), None)
                val = f"{r['ttft']:.2f}s" if r and "ttft" in r else "-"
                print(f"{val:>{col_width}}", end="")
            print()

            # Generation time row — time from first token to last token
            print(f"{'Gen':>20}", end="")
            for run in scenario_runs:
                r = next((r for r in run["results"] if r["turn"] == turn_num and r.get("run", 1) == 1), None)
                val = f"{r['gen_time']:.2f}s" if r and "gen_time" in r else "-"
                print(f"{val:>{col_width}}", end="")
            print()

            # Total time row — what the user actually waits (TTFT + Gen)
            print(f"{'Total':>20}", end="")
            for run in scenario_runs:
                r = next((r for r in run["results"] if r["turn"] == turn_num and r.get("run", 1) == 1), None)
                val = f"{r['total']:.2f}s" if r and "total" in r else "-"
                print(f"{val:>{col_width}}", end="")
            print()
            print()  # Blank line between turns for readability

        # ── Aggregate summary ────────────────────────────────────────
        # Sum up all turns to show the total conversation time.
        # This is the number that matters most for "which setup is faster?"
        print(f"{'─' * 20}", end="")
        for _ in labels:
            print(f"{'─' * (col_width - 1):>{col_width}}", end="")
        print()

        # Total Prefill: cumulative time spent staring at a blank screen
        # Total Gen: cumulative time watching tokens stream
        # Total Time: the full conversation wall clock (Prefill + Gen for all turns)
        for metric_name, metric_key in [("Total Prefill", "ttft"), ("Total Gen", "gen_time"), ("Total Time", "total")]:
            print(f"{metric_name:>20}", end="")
            for run in scenario_runs:
                valid = [r for r in run["results"] if r.get("run", 1) == 1 and metric_key in r]
                val = sum(r[metric_key] for r in valid) if valid else 0
                print(f"{val:>{col_width - 1}.1f}s", end="")
            print()

        # Average generation speed (tok/s) across all turns
        print(f"{'Avg Gen tok/s':>20}", end="")
        for run in scenario_runs:
            valid = [r for r in run["results"] if r.get("run", 1) == 1 and "gen_tps" in r]
            val = sum(r["gen_tps"] for r in valid) / len(valid) if valid else 0
            print(f"{val:>{col_width - 1}.1f} ", end="")
        print()

        # ── Winner declaration ───────────────────────────────────────
        # The winner is whoever has the lowest total conversation time.
        # We also show how much slower each other setup was, both in
        # absolute seconds and as a percentage.
        print()
        totals = []
        for run in scenario_runs:
            valid = [r for r in run["results"] if r.get("run", 1) == 1 and "total" in r]
            totals.append(sum(r["total"] for r in valid) if valid else float("inf"))
        winner_idx = totals.index(min(totals))
        print(f"  Winner (fastest total): {labels[winner_idx]} ({totals[winner_idx]:.1f}s)")

        # Show the gap for each non-winner
        for i, (label, total) in enumerate(zip(labels, totals)):
            if i != winner_idx and total < float("inf"):
                diff = total - totals[winner_idx]
                pct = diff / total * 100
                print(f"  {label}: +{diff:.1f}s slower ({pct:.0f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare results from multiple benchmark runs side by side"
    )
    parser.add_argument("files", nargs="+", metavar="RESULT_FILE",
                        help="Benchmark result JSON files to compare")
    args = parser.parse_args()
    compare(args.files)
