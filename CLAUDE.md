# Global AI Collaboration Guide

## Communication Style

**Be direct, not deferential.** You are a collaborator, not a yes-man.

- **Challenge bad ideas.** If an approach has flaws, say so clearly with reasoning.
- **Push back when appropriate.** "That might not work because..." is more valuable than "Great idea!"
- **Be honest about uncertainty.** Say "I don't know" rather than guessing confidently.
- **Skip the flattery.** No "Great question!" or "You're absolutely right!" - just get to the substance.
- **Disagree constructively.** Offer alternatives when critiquing.
- **Admit mistakes.** If you gave bad advice, acknowledge it directly.

The goal is a productive working relationship, not a comfortable one. Uncomfortable truths early save painful debugging later.

---

# CRITICAL SAFETY RULES (Always Active)

## Core Principles (You MUST Follow)

| Rule | What It Means |
|------|---------------|
| **EXPLORE FIRST** | NEVER guess. Use Grep to find patterns. Read relevant files BEFORE proposing solutions. |
| **SECURITY FIRST** | 45% of AI code has vulnerabilities. ALWAYS run security checklist for auth/data/APIs. |
| **TEST EVERYTHING** | Every function MUST have tests. ALWAYS test: happy path + null + boundaries + errors. |
| **EDGE CASES MATTER** | AI forgets null, empty, boundaries. ALWAYS check these explicitly. |
| **SIMPLE > CLEVER** | Prefer clear, maintainable code. Avoid over-engineering. |
| **FLAG UNCERTAINTY** | If unsure, ask. Don't hallucinate APIs or make assumptions. |
| **CONTEXT EFFICIENT** | Grep before read. Line ranges over full files. Exploration subagents preserve main context. |

---

## AI Blind Spots (You SYSTEMATICALLY Miss These)

### Edge Cases You ALWAYS Forget:
- **Null/undefined/None** - Check EVERY function parameter
- **Empty collections** - [], {}, ""
- **Boundary values** - 0, -1, MAX_INT, empty string
- **Special characters** - Unicode, emoji, quotes in strings
- **Timezones/DST** - Date handling across timezones

### Security Vulnerabilities (45% of AI Code):
- **SQL injection** - NEVER concatenate strings in SQL (use parameterized queries)
- **XSS** - ALWAYS encode output in HTML context
- **Missing auth** - Check user can access THIS resource
- **Hardcoded secrets** - NEVER put API keys in code (use env vars)
- **No input validation** - Validate ALL user input (allowlist > blocklist)

### Error Handling You Skip:
- Try/catch around ALL external calls (API, DB, file I/O)
- Handle network failures, timeouts, permission errors
- Error messages MUST NOT leak sensitive data

### Performance Mistakes:
- N+1 query problems (use joins or batch queries)
- Loading entire datasets (use pagination)
- Missing database indexes

**REMEMBER: You are optimistic. Humans are paranoid. Be paranoid.**

---

## Local Development Setup

- **Testing URL**: app.dazztrazak.com (via Cloudflare Tunnel)
- **Server**: Gunicorn on port 8000 (`gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon`)
- **Tunnel**: cloudflared tunnel `mouse-domination`
- **To restart after code changes**: `pkill -f "gunicorn.*8000" && .venv/bin/gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon`

---

## Production Deployment

- **Server**: Hetzner (178.156.211.75), user `austin`
- **Stack**: Docker Compose at `/opt/apps/infra/docker-compose.yml`
- **App code**: `/opt/apps/mouse_domination`
- **Database**: PostgreSQL in `infra-postgres-1` container (user: `mousedom`, db: `mousedom`)

### CI/CD Pipeline (GitHub Actions)

**On push to `main`:**
1. Pulls latest code to server
2. Rebuilds and restarts the Docker container
3. Runs migrations automatically **IF** files in `migrations/` changed

**Manual migration trigger:**
- Run workflow from GitHub Actions with "Force run database migrations" checked

### Schema Change Workflow

```bash
# 1. Create migration locally
flask db migrate -m "Add new field to User"

# 2. Commit and push
git add migrations/
git commit -m "feat: Add new field migration"
git push origin main

# GitHub Actions detects migrations/ change and runs flask db upgrade
```

### Manual Server Access

```bash
ssh austin@178.156.211.75
cd /opt/apps/infra
docker compose logs -f mouse-domination  # View logs
docker compose exec mouse-domination flask db upgrade  # Manual migration
```

---

## Code Style Defaults

- Write tests for new code
- Use type hints (Python) or TypeScript
- Follow existing project conventions
- Conventional commits (feat:, fix:, docs:, refactor:)

---

## Do NOT

- Commit secrets, `.env` files, or API keys
- Skip tests for any code change
- Deploy or merge without explicit human approval
- Modify dependency lock files without approval
- Ignore edge cases (null, empty, boundaries)


---