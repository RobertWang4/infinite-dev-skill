# Initializer Mode — First Session Setup

You are the initializer agent for a long-running autonomous development project. Your job is to set up the environment so that future coding sessions can make incremental progress efficiently.

This is the most important session — everything you create here will be used by every future coding agent.

## Step 1: Understand the Project

Look for a project specification in this order:
1. `app_spec.txt` or `spec.md` in the project directory
2. `README.md` with project description
3. If none found, ask the user to describe what they want to build

Read the spec carefully. Understand:
- What the final product should do
- The technology stack (or choose an appropriate one)
- The user's quality expectations

## Step 2: Generate `feature_list.json`

Create a comprehensive feature list that captures EVERYTHING the final product needs. This is the roadmap that all future sessions will follow.

### Format

```json
[
  {
    "id": 1,
    "category": "functional",
    "priority": 1,
    "description": "Brief description of what this feature does and what the test verifies",
    "steps": [
      "Step 1: Navigate to or set up the relevant context",
      "Step 2: Perform the core action",
      "Step 3: Verify the expected outcome"
    ],
    "depends_on": [],
    "passes": false
  }
]
```

### Requirements

- **Feature count by project scale:**
  - Small projects (CLI tools, simple scripts): **20-50 features**
  - Medium projects (single-page apps, REST APIs): **50-100 features**
  - Large projects (full-stack apps, complex systems): **100-200 features**
- **Categories**: `functional` (core behavior), `style` (UI/UX), `integration` (cross-feature), `performance` (speed/efficiency)
- **Priority ordering**: Fundamental features first (1 = highest priority). A chat app needs "send a message" before "export conversation"
- **Step detail**: Each feature should have 3-10 specific verification steps. At least 20 features should have 8+ steps for complex flows
- **`depends_on`**: optional array of feature IDs that must pass first. Use for features that clearly require other features to work (e.g., "delete a chat" depends on "create a chat"). Use `[]` or omit for independent features
- **All start as `false`** — nothing is passing yet
- **Be exhaustive** — it's better to have too many features than to miss something. Think about edge cases, error states, empty states, loading states

### Feature Writing Tips

Think like a QA engineer writing acceptance tests:
- "User can create a new account with email and password" (not "authentication works")
- "Error message appears when submitting empty form" (not "form validation")
- "Sidebar collapses on mobile viewport" (not "responsive design")
- "Previously sent messages persist after page reload" (not "data persistence")

### Web App Features Should Cover

- Navigation and routing
- Core CRUD operations for each entity
- Form validation and error handling
- Loading states and empty states
- Responsive design breakpoints
- Keyboard shortcuts and accessibility
- Dark/light theme if applicable
- Error recovery (network failures, invalid data)
- Performance (page load time, interaction responsiveness)

### Non-Web Project Features Should Cover

- CLI commands and flags
- Input validation and error messages
- File I/O operations
- Edge cases (empty input, large input, invalid input)
- Configuration handling
- Output format correctness
- Integration with external services

## Step 3: Create `init.sh`

Write a setup script that any future coding agent can run to get the development environment ready.

```bash
#!/bin/bash
# init.sh — Development environment setup
# Run this at the start of each coding session

set -e

echo "=== Setting up development environment ==="

# Install dependencies
# npm install / pip install / cargo build / etc.

# Start development servers (in background)
# npm run dev &
# python manage.py runserver &

# Wait for servers to be ready
# sleep 3

# Print access information
echo "=== Environment ready ==="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "================================"
```

The script should:
- Install all dependencies
- Start necessary servers in the background
- Wait for servers to be ready
- Print access URLs and port information
- Be idempotent (safe to run multiple times)

## Step 4: Initialize Git Repository

```bash
git init
git add -A
git commit -m "Initial project scaffold with feature list and init script"
```

## Step 5: Create Project Structure

Based on the tech stack, create the directory structure:

### Web App Example
```
src/
├── frontend/     # React/Vue/etc.
├── backend/      # Express/FastAPI/etc.
├── shared/       # Shared types/utilities
└── tests/        # Test files
```

### CLI/Library Example
```
src/
├── lib/          # Core library code
├── cli/          # CLI entry point
└── tests/        # Test files
```

Set up the basic configuration files (package.json, tsconfig, pyproject.toml, etc.)

## Step 6: Write Initial `claude-progress.txt`

```
# Project Progress

## Session 1 — Initialization
- Created feature_list.json with N features
- Set up project scaffold with [tech stack]
- Created init.sh for environment setup
- Initialized git repository

## Status
- Features passing: 0/N (0%)
- Current focus: Ready to begin feature implementation
- Next session should: Start with feature #1 (highest priority)

## Architecture Notes
[Brief description of key architectural decisions]
```

## Step 7: Begin Implementation (if time allows)

If you still have context capacity, begin implementing the highest-priority features. Follow the same protocol as the coding agent:
1. Pick feature #1
2. Implement it
3. Test end-to-end
4. Mark as passing in `feature_list.json`
5. Commit

## Critical Rules

1. **The feature list is sacred.** Future sessions depend on it being comprehensive and well-ordered. Spend real time on this — it's the most impactful thing you do.

2. **All features start as `false`.** Never pre-mark anything as passing.

3. **Priority order matters.** Foundation features (project runs, basic navigation, data model) must come before advanced features (search, sharing, settings).

4. **Leave the environment clean.** Commit everything, document everything. The next agent starts with zero memory of what you did.

5. **init.sh must work.** Test it. The next agent's first action is running this script.
