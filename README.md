# infinite-dev

A Claude Code skill that turns Claude into an infinite development loop: spec → feature list → implement → test → commit → repeat — across unlimited context windows.

Based on Anthropic's research: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

---

## Workflow

```
                        ┌─────────────────────────────────┐
                        │          PROJECT FILES           │
                        │                                  │
                        │  AGENTS.md    feature_list.json  │
                        │  init.sh      claude-progress.txt│
                        │  dev-agent.py  src/              │
                        └───────────────┬─────────────────┘
                                        │
                                        ▼
┌───────────────────────────────────────────────────────────────┐
│                      FIRST SESSION                            │
│                                                               │
│  User Spec ──► Initializer Agent                              │
│                    │                                          │
│                    ├── Generate feature_list.json (20-200)     │
│                    ├── Create init.sh (idempotent)             │
│                    ├── Initialize git repo + scaffold          │
│                    ├── Write claude-progress.txt               │
│                    └── Ask user: Mode A or Mode B?             │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                   PER-FEATURE WORKFLOW                         │
│                                                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │ STEP 1   │──►│ STEP 2   │──►│ STEP 3   │──►│ STEP 4   │   │
│  │ Init Env │   │ Pick     │   │ Write    │   │ Verify   │   │
│  │ ./init.sh│   │ Feature  │   │ Code     │   │          │   │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘   │
│                                                     │         │
│                                  ┌──────────────────┤         │
│                                  │                  │         │
│                             ┌────▼─────┐  ┌────────▼──────┐  │
│                             │ npm run  │  │  Browser Test  │  │
│                             │ lint     │  │  (Playwright)  │  │
│                             └────┬─────┘  └────────┬──────┘  │
│                                  │                  │         │
│                             ┌────▼─────┐            │         │
│                             │ npm run  │            │         │
│                             │ build    │            │         │
│                             └────┬─────┘            │         │
│                                  │                  │         │
│                                  └────────┬─────────┘         │
│                                           │                   │
│                                     ┌─────▼─────┐            │
│                                     │ All pass? │            │
│                                     └─────┬─────┘            │
│                              ┌────────────┼────────────┐      │
│                              │ NO         │ YES        │      │
│                              ▼            │            ▼      │
│                        ┌──────────┐       │     ┌──────────┐  │
│                        │ Fix      │       │     │ STEP 5   │  │
│                        │ Errors   │───────┘     │ Complete │  │
│                        └────┬─────┘             │ + Log    │  │
│                             │ stuck?            └────┬─────┘  │
│                             ▼                        │        │
│                        ┌──────────┐            ┌─────▼─────┐  │
│                        │ Skip +   │            │ STEP 6    │  │
│                        │ Revert   │            │ Commit    │  │
│                        └────┬─────┘            └─────┬─────┘  │
│                             │                        │        │
│                             └────────────┬───────────┘        │
│                                          │                    │
│                             ◄── next feature ──►              │
└──────────────────────────────────┬────────────────────────────┘
                                   │
                   ┌───────────────┼───────────────┐
                   ▼                               ▼
    ┌───────────────────────┐       ┌───────────────────────┐
    │   MODE A: Interactive │       │   MODE B: Autopilot   │
    │                       │       │                       │
    │  Claude implements    │       │  dev-agent.py run     │
    │  directly in session  │       │  spawns claude -p     │
    │                       │       │  per feature          │
    │  /clear + "go ahead"  │       │                       │
    │  to reset context     │       │  auto context reset   │
    │                       │       │  fully unattended     │
    │  ✓ MCP/Playwright     │       │                       │
    │  ✓ No special perms   │       │  ✗ Needs --danger..   │
    │  ✓ See every step     │       │  ✗ MCP may not work   │
    │  △ Occasional /clear  │       │  ✗ Can't see live     │
    └───────────────────────┘       └───────────────────────┘

State Persistence (across all context windows):
  feature_list.json  ◄── source of truth, only "passes" flips
  claude-progress.txt ◄── structured session notes (What/Testing/Notes)
  git history         ◄── code changes + descriptive commits
```

---

## Quick Start

```bash
# 1. Copy files to your project
cp ~/.claude/skills/infinite-dev/scripts/dev-agent.py ./dev-agent.py
cp ~/.claude/skills/infinite-dev/templates/AGENTS.md ./AGENTS.md

# 2. Tell Claude what to build
> Build me a task management app with React and Express

# Claude reads AGENTS.md → generates feature_list.json → asks Mode A or B → starts building
```

---

## Mode A: Interactive (Recommended)

Claude implements features in your current session. You `/clear` between batches.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Claude   │────►│  init +  │────►│  Pick +  │────►│  Test +  │
│  reads    │     │  status  │     │  Code    │     │  Commit  │
│ AGENTS.md │     │          │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └─────┬────┘
     ▲                                                    │
     │              ┌────────────────────────┐            │
     │              │  Context getting long? │◄───────────┘
     │              └───────────┬────────────┘
     │                 NO │          │ YES
     │                    ▼          ▼
     │              ┌─────────┐  ┌──────────────────────────┐
     │              │ Next    │  │ "Done N features.        │
     │              │ feature │  │  /clear then go ahead."  │
     │              └────┬────┘  └────────────┬─────────────┘
     │                   │                    │
     │                   │              User: /clear
     │                   │              User: go ahead
     │                   │                    │
     └───────────────────┴────────────────────┘
```

## Mode B: Autopilot (Fully Autonomous)

`dev-agent.py run` spawns a fresh `claude -p` process per feature. No human interaction needed.

```
┌──────────────────────────────────────────────────────┐
│  python dev-agent.py run                             │
│                                                      │
│  while features remaining:                           │
│    ┌─────────────────────────────────────────────┐   │
│    │  claude -p  (fresh context, fresh process)  │   │
│    │                                             │   │
│    │  implement → lint → build → test            │   │
│    │  → complete → commit → log → exit           │   │
│    └─────────────────────────────────────────────┘   │
│    │                                                 │
│    ▼                                                 │
│    context destroyed → next feature                  │
│                                                      │
│  done → final report                                 │
└──────────────────────────────────────────────────────┘
```

```bash
python dev-agent.py run                     # Use CLI default model
python dev-agent.py run --max-features 10   # Limit per run
python dev-agent.py run --timeout 3600      # 1 hour per feature
python dev-agent.py run --model <name>      # Override model
```

---

## Feature List Format

```json
[
  {
    "id": 1,
    "category": "functional",
    "priority": 1,
    "description": "User can create a new chat and send a message",
    "steps": [
      "Navigate to main interface",
      "Click 'New Chat' button",
      "Type a message",
      "Press Enter",
      "Verify AI response appears"
    ],
    "depends_on": [],
    "passes": false
  }
]
```

- `priority`: 1 = highest, lower numbers go first
- `depends_on`: feature IDs that must pass first
- `passes`: `false` → `true` (passing) / `"skipped"` (blocked)
- Never delete, reorder, or modify descriptions

## CLI Reference

| Command | Description |
|---------|-------------|
| `dev-agent.py run` | Autopilot: one claude -p per feature |
| `dev-agent.py status` | Show progress (passing/total/skipped) |
| `dev-agent.py next` | Show next feature to implement |
| `dev-agent.py complete <id>` | Mark feature as passing |
| `dev-agent.py skip <id> "reason"` | Skip a blocked feature |
| `dev-agent.py regression` | Pick 1-2 passing features to re-verify |
| `dev-agent.py log --feature-id <id> --done "..." --testing "..." --notes "..."` | Structured progress log |

## Testing Strategy

| Project Type | Testing Method |
|-------------|----------------|
| Web apps | Playwright MCP — browser automation + screenshots |
| CLI tools | pytest / jest / go test / cargo test |
| APIs | Integration tests + endpoint verification |
| All types | Regression testing of previously passing features |

## Team Mode (Advanced)

For maximum throughput, run multiple features in parallel:

```
Claude (Team Lead)
  ├── git worktree A → Feature #3 (Agent 1)
  ├── git worktree B → Feature #4 (Agent 2)
  ├── git worktree C → Feature #5 (Agent 3)
  └── Merge all → Regression test → Continue
```

## File Structure

```
infinite-dev/
├── SKILL.md              # Skill entry point (Claude reads this)
├── README.md             # This file
├── scripts/
│   └── dev-agent.py      # CLI: state management + autopilot loop
└── templates/
    └── AGENTS.md         # Template → copy to project root
```

## Credits

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic Engineering
- [claude-quickstarts/autonomous-coding](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) — Reference implementation

## License

MIT
