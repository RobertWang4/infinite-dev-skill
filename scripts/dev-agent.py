#!/usr/bin/env python3
"""
dev-agent.py — CLI tool for Claude to manage infinite-dev workflow.

Claude calls this script via Shell to get tasks, mark progress, run autonomously.
All workflow logic lives here, keeping it OUT of Claude's context window.

Usage (Claude runs these via Shell):
    python dev-agent.py status              # Show progress summary
    python dev-agent.py next                # Get next feature to implement
    python dev-agent.py find-parallel       # Show parallelizable features
    python dev-agent.py complete <id>       # Mark feature as passing
    python dev-agent.py skip <id> <reason>  # Mark feature as skipped
    python dev-agent.py regression          # Pick 1-2 passing features to verify
    python dev-agent.py log <message>       # Append to claude-progress.txt
    python dev-agent.py run                 # Autonomous loop: spawns claude -p per feature
    python dev-agent.py run --parallel 3    # Run 3 features in parallel (worktree isolation)
    python dev-agent.py run --max-features 5  # Limit to 5 features per run
"""

import argparse
import json
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def load_features(project_dir: Path) -> list[dict]:
    path = project_dir / "feature_list.json"
    if not path.exists():
        print("ERROR: feature_list.json not found. Run initializer first.", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def save_features(project_dir: Path, features: list[dict]):
    path = project_dir / "feature_list.json"
    with open(path, "w") as f:
        json.dump(features, f, indent=2, ensure_ascii=False)
    print(f"Updated {path}")


def get_passing_ids(features: list[dict]) -> set[int]:
    return {f["id"] for f in features if f.get("passes") is True}


def cmd_status(project_dir: Path, **_):
    features = load_features(project_dir)
    total = len(features)
    passing = sum(1 for f in features if f.get("passes") is True)
    skipped = sum(1 for f in features if f.get("passes") == "skipped")
    remaining = total - passing - skipped
    pct = (passing / total * 100) if total else 0

    print(f"Progress: {passing}/{total} passing ({pct:.1f}%)")
    if skipped:
        print(f"Skipped: {skipped}")
    print(f"Remaining: {remaining}")
    print()

    progress_file = project_dir / "claude-progress.txt"
    if progress_file.exists():
        content = progress_file.read_text().strip()
        lines = content.split("\n")
        print("Last progress notes:")
        for line in lines[-10:]:
            print(f"  {line}")


def find_next_feature(features: list[dict]) -> dict | None:
    """Find the highest-priority feature with all deps met."""
    passing_ids = get_passing_ids(features)
    for f in sorted(features, key=lambda x: x.get("priority", 999)):
        if f.get("passes") is True or f.get("passes") == "skipped":
            continue
        deps = f.get("depends_on", [])
        if deps and not all(d in passing_ids for d in deps):
            continue
        return f
    return None


def find_next_features(features: list[dict], n: int) -> list[dict]:
    """Find up to N mutually-independent features that can run in parallel."""
    passing_ids = get_passing_ids(features)
    candidates = []
    for f in sorted(features, key=lambda x: x.get("priority", 999)):
        if f.get("passes") is True or f.get("passes") == "skipped":
            continue
        deps = f.get("depends_on", [])
        if deps and not all(d in passing_ids for d in deps):
            continue
        candidates.append(f)

    selected = []
    selected_ids = set()
    for f in candidates:
        deps = set(f.get("depends_on", []))
        if not deps & selected_ids:
            selected.append(f)
            selected_ids.add(f["id"])
            if len(selected) >= n:
                break
    return selected


def cmd_find_parallel(project_dir: Path, count: int = 3, **_):
    """Show parallelizable features and remaining count."""
    features = load_features(project_dir)
    remaining = sum(1 for f in features if f.get("passes") not in (True, "skipped"))
    batch = find_next_features(features, count)

    print(f"Remaining features: {remaining}")
    print(f"Parallelizable features found: {len(batch)}")
    if len(batch) >= 2:
        print(f"\nCan run in parallel:")
        for f in batch:
            print(f"  #{f['id']}: {f['description']}")
        print(f"\nMode A: use Agent tool + worktree for each")
        print(f"Mode B: python dev-agent.py run --parallel {len(batch)}")
    else:
        print("Not enough independent features for parallel execution.")


def cmd_next(project_dir: Path, **_):
    features = load_features(project_dir)
    f = find_next_feature(features)
    if f:
        print(f"NEXT FEATURE: #{f['id']} (priority {f.get('priority', '?')})")
        print(f"Description: {f['description']}")
        print(f"Category: {f.get('category', 'functional')}")
        if f.get("depends_on"):
            print(f"Depends on: {f['depends_on']}")
        print(f"\nSteps:")
        for i, step in enumerate(f.get("steps", []), 1):
            print(f"  {i}. {step}")
        return

    passing_ids = get_passing_ids(features)
    passing = len(passing_ids)
    total = len(features)
    if passing == total:
        print("ALL FEATURES COMPLETE!")
    else:
        print("NO AVAILABLE FEATURES — remaining features have unmet dependencies or are skipped.")
        print("\nBlocked features:")
        for f in features:
            if f.get("passes") is True or f.get("passes") == "skipped":
                continue
            deps = f.get("depends_on", [])
            missing = [d for d in deps if d not in passing_ids]
            if missing:
                print(f"  #{f['id']}: {f['description']} (waiting on {missing})")


def cmd_complete(project_dir: Path, feature_id: int, **_):
    features = load_features(project_dir)
    for f in features:
        if f["id"] == feature_id:
            if f.get("passes") is True:
                print(f"Feature #{feature_id} is already passing.")
                return
            f["passes"] = True
            save_features(project_dir, features)
            passing = sum(1 for feat in features if feat.get("passes") is True)
            total = len(features)
            print(f"✅ Feature #{feature_id} marked as PASSING ({passing}/{total})")
            return
    print(f"ERROR: Feature #{feature_id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_skip(project_dir: Path, feature_id: int, reason: str = "", **_):
    features = load_features(project_dir)
    for f in features:
        if f["id"] == feature_id:
            f["passes"] = "skipped"
            save_features(project_dir, features)
            print(f"⏭️ Feature #{feature_id} marked as SKIPPED")
            if reason:
                _append_structured_progress(
                    project_dir, feature_id, f["description"],
                    done=f"- Skipped: {reason}",
                    testing="- N/A (skipped)",
                    notes=f"- Feature blocked, may retry later",
                )
                print(f"Logged reason to claude-progress.txt")
            return
    print(f"ERROR: Feature #{feature_id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_regression(project_dir: Path, **_):
    features = load_features(project_dir)
    passing = [f for f in features if f.get("passes") is True]
    if not passing:
        print("No passing features to regression-test.")
        return
    sample = random.sample(passing, min(2, len(passing)))
    print("REGRESSION CHECK — verify these still pass:")
    for f in sample:
        print(f"\n  #{f['id']}: {f['description']}")
        for i, step in enumerate(f.get("steps", []), 1):
            print(f"    {i}. {step}")
    print("\nIf any fail: fix the regression, then run `python dev-agent.py complete <id>` or mark as failing manually.")


def cmd_log(project_dir: Path, feature_id: int = 0,
            done: str = "", testing: str = "", notes: str = "",
            message: str = "", **_):
    if not done and not message:
        print("ERROR: Provide --done or a plain message.", file=sys.stderr)
        sys.exit(1)

    if done:
        features = load_features(project_dir)
        desc = ""
        for f in features:
            if f["id"] == feature_id:
                desc = f["description"]
                break
        _append_structured_progress(project_dir, feature_id, desc, done, testing, notes)
    else:
        _append_plain_progress(project_dir, message)

    print("Logged to claude-progress.txt")


def _append_plain_progress(project_dir: Path, message: str):
    path = project_dir / "claude-progress.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a") as f:
        f.write(f"\n[{timestamp}] {message}\n")


def _append_structured_progress(project_dir: Path, feature_id: int,
                                description: str, done: str,
                                testing: str = "", notes: str = ""):
    path = project_dir / "claude-progress.txt"
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"""
---

## {date} — Feature #{feature_id}: {description}

### What was done:
{done}

### Testing:
{testing or '- (not recorded)'}

### Notes:
{notes or '- (none)'}
"""
    with open(path, "a") as f:
        f.write(entry)


# ---------------------------------------------------------------------------
# Autonomous run — spawns claude -p per feature
# ---------------------------------------------------------------------------

def _create_worktree(project_dir: Path, feature_id: int) -> Path | None:
    """Create a git worktree for a feature. Returns worktree path or None on failure."""
    wt_dir = project_dir / ".worktrees"
    wt_dir.mkdir(exist_ok=True)
    wt_path = wt_dir / f"feature-{feature_id}"
    branch = f"feature-{feature_id}"
    try:
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", branch],
            cwd=str(project_dir), capture_output=True, text=True, check=True,
        )
        return wt_path
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] Failed to create worktree for feature #{feature_id}: {e.stderr.strip()}")
        return None


def _remove_worktree(project_dir: Path, feature_id: int):
    """Remove worktree and its branch."""
    wt_path = project_dir / ".worktrees" / f"feature-{feature_id}"
    branch = f"feature-{feature_id}"
    try:
        subprocess.run(
            ["git", "worktree", "remove", str(wt_path), "--force"],
            cwd=str(project_dir), capture_output=True, text=True,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=str(project_dir), capture_output=True, text=True,
        )
    except Exception:
        pass


def _merge_worktree(project_dir: Path, feature_id: int) -> bool:
    """Merge feature branch back into current branch. Returns True on success."""
    branch = f"feature-{feature_id}"
    try:
        result = subprocess.run(
            ["git", "merge", "--no-ff", branch, "-m", f"merge: feature #{feature_id} from parallel run"],
            cwd=str(project_dir), capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  [CONFLICT] Merge failed for feature #{feature_id}, aborting merge")
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=str(project_dir), capture_output=True, text=True,
            )
            return False
        return True
    except Exception as e:
        print(f"  [ERROR] Merge error for feature #{feature_id}: {e}")
        return False


def run_parallel_batch(project_dir: Path, batch: list[dict], passing: int, total: int,
                       model: str, max_turns: int, timeout: int) -> list[int]:
    """Run a batch of features in parallel using worktrees. Returns list of completed feature IDs."""
    worktrees = {}  # feature_id -> worktree_path
    procs = {}      # feature_id -> Popen

    # 1. Create worktrees and start processes
    for feature in batch:
        fid = feature["id"]
        wt_path = _create_worktree(project_dir, fid)
        if not wt_path:
            continue
        worktrees[fid] = wt_path

        system_prompt = FEATURE_SYSTEM_PROMPT.format(
            feature_id=fid,
            description=feature["description"],
            pass_count=f"{passing + 1}/{total}",
        )
        user_prompt = build_feature_prompt(feature, passing, total)

        cmd = [
            "claude", "-p",
            "--dangerously-skip-permissions",
            "--max-turns", str(max_turns),
            "--system-prompt", system_prompt,
        ]
        if model:
            cmd.extend(["--model", model])

        print(f"  Starting feature #{fid} in {wt_path}...")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(wt_path.resolve()),
        )
        proc.stdin.write(user_prompt)
        proc.stdin.close()
        procs[fid] = proc

    if not procs:
        print("  No parallel processes started.")
        return []

    # 2. Wait for all processes
    print(f"  Waiting for {len(procs)} parallel sessions...")
    completed_ids = []
    for fid, proc in procs.items():
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            if proc.returncode == 0:
                print(f"  ✅ Feature #{fid} session finished")
                output_lines = stdout.strip().split("\n") if stdout else []
                for line in output_lines[-5:]:
                    print(f"    {line}")
            else:
                print(f"  ❌ Feature #{fid} session failed (exit {proc.returncode})")
                if stderr:
                    print(f"    {stderr[:300]}")
        except subprocess.TimeoutExpired:
            print(f"  ⏱️ Feature #{fid} timed out, killing...")
            proc.kill()
            proc.wait()

    # 3. Merge completed branches and clean up
    for fid in list(worktrees.keys()):
        # Check if feature was marked complete in the worktree's copy
        wt_path = worktrees[fid]
        wt_features_path = wt_path / "feature_list.json"
        merged = False
        if wt_features_path.exists():
            with open(wt_features_path) as f:
                wt_features = json.load(f)
            for wf in wt_features:
                if wf["id"] == fid and wf.get("passes") is True:
                    # Feature was completed in worktree, merge it
                    if _merge_worktree(project_dir, fid):
                        completed_ids.append(fid)
                        print(f"  🔀 Merged feature #{fid}")
                        merged = True
                    else:
                        print(f"  ⚠️ Feature #{fid} completed but merge failed, skipping")
                    break

        if not merged:
            print(f"  ⏭️ Feature #{fid} not completed in worktree, skipping merge")

        _remove_worktree(project_dir, fid)
        print(f"  🧹 Cleaned up worktree for feature #{fid}")

    return completed_ids

FEATURE_SYSTEM_PROMPT = """You are an expert developer. Every session follows this MANDATORY workflow.

## Step 1: Initialize Environment

If init.sh exists, run it:
```bash
chmod +x init.sh && ./init.sh
```
**DO NOT skip this step.** Ensure the dev server is running before proceeding.

## Step 2: Read Context

- Read claude-progress.txt to understand what previous sessions did.
- Read relevant source files to understand existing code patterns.

## Step 3: Implement the Feature

You are implementing ONLY this one feature:
  Feature #{feature_id}: {description}

- Read the feature description and steps carefully.
- Implement the functionality to satisfy ALL steps.
- Follow existing code patterns and conventions.

## Step 4: Test Thoroughly

After implementation, verify ALL steps in the feature:
- Write unit tests if applicable.
- Use browser testing for UI features (MCP Playwright tools: browser_navigate, browser_snapshot, browser_click, browser_type, browser_take_screenshot).
- Run linter and build to catch errors:
  - Python projects: run pytest, ruff/flake8 if configured
  - Node projects: run npm run lint and npm run build in the project directory
  - Other: run the project's configured test/lint commands
- **Fix any errors before proceeding.** Do not skip failing tests.

## Step 5: Update Progress

If all tests pass, run these commands IN ORDER:
```
python dev-agent.py complete {feature_id}
git add -A && git commit -m "feat: {description} [{pass_count} passing]"
python dev-agent.py log --feature-id {feature_id} --done "- list of specific changes made" --testing "- how it was tested, what was verified" --notes "- any relevant decisions, gotchas, or tips for future agents"
```

## If Blocked

If stuck after 2-3 attempts:
```
python dev-agent.py skip {feature_id} "reason why it's blocked"
git checkout -- . && git clean -fd
```

## IMPORTANT

- Do NOT modify feature descriptions or steps in feature_list.json.
- Do NOT work on any other feature.
- Leave the project in a clean git state (git status clean) when done."""


def build_feature_prompt(feature: dict, passing: int, total: int) -> str:
    steps_text = "\n".join(f"  {i}. {s}" for i, s in enumerate(feature.get("steps", []), 1))
    return f"""Implement this feature for the project.

Current progress: {passing}/{total} features passing.

FEATURE #{feature['id']} (priority {feature.get('priority', '?')}, category: {feature.get('category', 'functional')}):
  {feature['description']}

Steps:
{steps_text}

Start by reading claude-progress.txt and the relevant source files to understand the current state.
If init.sh exists, run it first to set up the environment."""


def run_one_feature(project_dir: Path, feature: dict, passing: int, total: int,
                    model: str, max_turns: int, timeout: int) -> bool:
    """Spawn a single claude -p session for one feature. Returns True if session succeeded."""
    system_prompt = FEATURE_SYSTEM_PROMPT.format(
        feature_id=feature["id"],
        description=feature["description"],
        pass_count=f"{passing + 1}/{total}",
    )
    user_prompt = build_feature_prompt(feature, passing, total)

    cmd = [
        "claude", "-p",
        "--dangerously-skip-permissions",
        "--max-turns", str(max_turns),
        "--system-prompt", system_prompt,
    ]

    if model:
        cmd.extend(["--model", model])

    print(f"\n  Spawning claude -p for feature #{feature['id']}...")

    try:
        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            cwd=str(project_dir.resolve()),
            timeout=timeout,
        )

        if result.returncode != 0:
            print(f"  [ERROR] claude -p exited with code {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
            return False

        output_lines = result.stdout.strip().split("\n")
        if len(output_lines) > 15:
            print("  ... (output truncated) ...")
        for line in output_lines[-15:]:
            print(f"  {line}")

        return True

    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Session exceeded {timeout}s")
        return False
    except FileNotFoundError:
        print("  [ERROR] 'claude' CLI not found. Install: npm install -g @anthropic-ai/claude-code")
        return False


def cmd_run(project_dir: Path, model: str = "",
            max_features: int = 0, max_turns: int = 150,
            timeout: int = 1800, delay: int = 3, parallel: int = 1, **_):
    """Autonomous development loop. Each feature gets a fresh claude -p process."""
    features = load_features(project_dir)
    total = len(features)
    completed_this_run = 0
    consecutive_errors = 0

    print("=" * 60)
    print("  INFINITE DEV — Autonomous Run")
    print(f"  Project: {project_dir.resolve()}")
    print(f"  Model: {model or '(CLI default)'}")
    print(f"  Max features: {'unlimited' if max_features == 0 else max_features}")
    print(f"  Timeout per feature: {timeout}s")
    print(f"  Parallel: {parallel}")
    print("=" * 60)

    while True:
        if max_features > 0 and completed_this_run >= max_features:
            print(f"\n  Reached max features limit ({max_features}). Stopping.")
            break

        features = load_features(project_dir)
        passing = sum(1 for f in features if f.get("passes") is True)
        skipped = sum(1 for f in features if f.get("passes") == "skipped")
        total = len(features)
        pct = (passing / total * 100) if total else 0

        print(f"\n{'─' * 60}")
        print(f"  Progress: {passing}/{total} ({pct:.1f}%)" +
              (f", {skipped} skipped" if skipped else ""))

        if passing + skipped >= total:
            print(f"\n  All features processed! {passing} passing, {skipped} skipped.")
            break

        # --- Parallel mode ---
        if parallel > 1:
            batch = find_next_features(features, parallel)
            if not batch:
                print("\n  No available features (deps unmet or all skipped).")
                break
            if len(batch) == 1:
                # Only one available — fall through to sequential
                pass
            else:
                remaining_budget = max_features - completed_this_run if max_features > 0 else len(batch)
                batch = batch[:remaining_budget]
                print(f"  Running {len(batch)} features in parallel...")
                for f in batch:
                    print(f"    #{f['id']}: {f['description']}")

                completed_ids = run_parallel_batch(
                    project_dir, batch, passing, total,
                    model=model, max_turns=max_turns, timeout=timeout,
                )

                if completed_ids:
                    consecutive_errors = 0
                    completed_this_run += len(completed_ids)
                    print(f"  Batch done: {len(completed_ids)}/{len(batch)} features completed")
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        print(f"\n  3 consecutive batches with no progress. Stopping.")
                        _append_plain_progress(project_dir, f"Auto-run stopped: 3 consecutive failed batches")
                        break

                if delay > 0:
                    time.sleep(delay)
                continue

        # --- Sequential mode (parallel=1 or single feature available) ---
        nf = find_next_feature(features)
        if not nf:
            print("\n  No available features (deps unmet or all skipped).")
            break

        print(f"  Next: #{nf['id']} — {nf['description']}")

        success = run_one_feature(
            project_dir, nf, passing, total,
            model=model, max_turns=max_turns, timeout=timeout,
        )

        if success:
            consecutive_errors = 0
            features_after = load_features(project_dir)
            new_passing = sum(1 for f in features_after if f.get("passes") is True)
            if new_passing > passing:
                completed_this_run += 1
                print(f"  ✅ Feature #{nf['id']} completed ({new_passing}/{total})")
            else:
                print(f"  ⚠️ Session finished but feature #{nf['id']} not marked complete")
        else:
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print(f"\n  3 consecutive errors. Stopping.")
                _append_plain_progress(project_dir, f"Auto-run stopped: 3 consecutive errors at feature #{nf['id']}")
                break

        if delay > 0:
            time.sleep(delay)

    features = load_features(project_dir)
    passing = sum(1 for f in features if f.get("passes") is True)
    skipped = sum(1 for f in features if f.get("passes") == "skipped")
    total = len(features)
    pct = (passing / total * 100) if total else 0

    print(f"\n{'=' * 60}")
    print(f"  RUN COMPLETE")
    print(f"  Features completed this run: {completed_this_run}")
    print(f"  Total progress: {passing}/{total} ({pct:.1f}%)" +
          (f", {skipped} skipped" if skipped else ""))
    print(f"{'=' * 60}")

    _append_plain_progress(project_dir,
        f"Auto-run finished: +{completed_this_run} features, now {passing}/{total} ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Infinite Dev — CLI task manager for Claude")
    parser.add_argument("--project-dir", "-d", type=Path, default=Path("."),
                        help="Project directory (default: current dir)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show progress summary")
    sub.add_parser("next", help="Get next feature to implement")

    p_parallel = sub.add_parser("find-parallel", help="Show parallelizable features")
    p_parallel.add_argument("--count", "-n", type=int, default=3,
                            help="Max number of parallel features to find (default: 3)")

    p_complete = sub.add_parser("complete", help="Mark feature as passing")
    p_complete.add_argument("feature_id", type=int)

    p_skip = sub.add_parser("skip", help="Mark feature as skipped")
    p_skip.add_argument("feature_id", type=int)
    p_skip.add_argument("reason", nargs="?", default="")

    sub.add_parser("regression", help="Pick passing features to verify")

    p_log = sub.add_parser("log", help="Append structured or plain entry to progress file")
    p_log.add_argument("message", nargs="?", default="", help="Plain message (shorthand)")
    p_log.add_argument("--feature-id", type=int, default=0, help="Feature ID for structured entry")
    p_log.add_argument("--done", default="", help="What was done (structured entry)")
    p_log.add_argument("--testing", default="", help="How it was tested (structured entry)")
    p_log.add_argument("--notes", default="", help="Notes for future agents (structured entry)")

    p_run = sub.add_parser("run", help="Autonomous loop: spawn claude -p per feature")
    p_run.add_argument("--model", "-m", default="",
                        help="Claude model (default: use claude CLI's configured model)")
    p_run.add_argument("--max-features", type=int, default=0,
                        help="Max features to complete (0 = unlimited)")
    p_run.add_argument("--max-turns", type=int, default=150,
                        help="Max tool-use turns per feature session (default: 150)")
    p_run.add_argument("--timeout", "-t", type=int, default=1800,
                        help="Timeout per feature in seconds (default: 1800)")
    p_run.add_argument("--delay", type=int, default=3,
                        help="Seconds between sessions (default: 3)")
    p_run.add_argument("--parallel", type=int, default=1,
                        help="Number of features to run in parallel (default: 1, sequential)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        "status": cmd_status,
        "next": cmd_next,
        "find-parallel": cmd_find_parallel,
        "complete": cmd_complete,
        "skip": cmd_skip,
        "regression": cmd_regression,
        "log": cmd_log,
        "run": cmd_run,
    }
    kwargs = vars(args)
    command = kwargs.pop("command")
    cmd_map[command](**kwargs)


if __name__ == "__main__":
    main()
