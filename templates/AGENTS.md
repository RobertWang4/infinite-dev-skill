# Infinite Dev — Autonomous Coding Agent

Every new agent session MUST follow this workflow.

## Choose Your Mode

This project supports two execution modes. Pick ONE:

- **Mode A (Interactive)**: Claude implements features directly, you /clear between features. Better visibility, MCP/Playwright works, no extra permissions needed.
- **Mode B (Autopilot)**: Claude runs `python dev-agent.py run` which spawns separate processes. Fully autonomous, but needs `--dangerously-skip-permissions` and MCP may not work.

---

## Mode A: Interactive (recommended for most projects)

### Step 1: Initialize Environment

```bash
chmod +x init.sh && ./init.sh
```

**DO NOT skip this step.** Ensure the dev server / environment is running before proceeding.

### Step 2: Orient

```bash
python dev-agent.py status
python dev-agent.py next
```

If feature_list.json does not exist yet, initialize the project first:
1. Read the project spec (spec.md, app_spec.txt, README, or ask the user)
2. Generate feature_list.json with 20-200 features
3. Create init.sh for environment setup
4. Create claude-progress.txt
5. Then continue

### Step 3: Implement the Feature

- Read the feature description and steps from `dev-agent.py next` output.
- Implement the functionality to satisfy ALL steps.
- Follow existing code patterns and conventions.

### Step 4: Test Thoroughly

- Write unit tests if applicable.
- Use browser testing for UI features (MCP Playwright tools).
- Run linter and build:
  - Python: pytest, ruff/flake8
  - Node: npm run lint && npm run build
- **Fix any errors before proceeding.**

### Step 5: Record & Commit

```bash
python dev-agent.py complete <feature_id>
git add -A && git commit -m "feat: <description> [<passing>/<total> passing]"
python dev-agent.py log --feature-id <id> --done "- changes" --testing "- how tested" --notes "- tips for future"
```

### Step 6: Next Feature or Clear

After completing a feature:
- If context is still short: go back to Step 2 immediately.
- If you've done 2+ features or context is getting long:
  - Ensure git status is clean.
  - Say: **"✅ 本轮完成 [N] 个 feature（[passing]/[total]）。输入 /clear 后发送 go ahead 继续。"**
  - Wait for user.

### If Blocked

After 2-3 failed attempts:
```bash
python dev-agent.py skip <id> "reason"
git checkout -- . && git clean -fd
```
Then go back to Step 2.

---

## Mode B: Autopilot (fully autonomous)

### Step 1: Initialize Environment

```bash
chmod +x init.sh && ./init.sh
```

### Step 2: Check State

```bash
python dev-agent.py status
```

If feature_list.json does not exist, initialize the project first (same as Mode A).

### Step 3: Start Autonomous Loop

```bash
python dev-agent.py run
```

Options:
```bash
python dev-agent.py run --max-features 10    # Limit per run
python dev-agent.py run --timeout 3600       # 1 hour per feature
python dev-agent.py run --model <name>       # Override model
```

This spawns a separate `claude -p` process for each feature. Each gets a clean context automatically. No /clear needed.

---

## Manual Commands (both modes)

| Command | Description |
|---------|-------------|
| `python dev-agent.py status` | Show progress |
| `python dev-agent.py next` | Show next feature |
| `python dev-agent.py complete <id>` | Mark feature passing |
| `python dev-agent.py skip <id> "reason"` | Skip a feature |
| `python dev-agent.py regression` | Pick features to re-verify |
| `python dev-agent.py log --feature-id <id> --done "..." --testing "..." --notes "..."` | Log structured progress |

## IMPORTANT

- Only mark `passes: true` after ALL steps in the feature are verified.
- Never delete or modify task descriptions in feature_list.json.
- Never remove tasks from the list.
- Run lint + build + browser tests before marking any feature as passing.
- Fix errors before proceeding — do not skip failing tests.
