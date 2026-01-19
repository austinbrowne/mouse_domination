# /update-docs - Project Documentation Update Prompt

## Purpose
Keep all project documentation accurate and up-to-date after significant changes.

## Documentation Files

### Core Reference Docs
| File | Purpose | Update Frequency |
|------|---------|------------------|
| `README.md` | Project overview, setup, usage | After features/setup changes |
| `CLAUDE.md` | AI assistant instructions | After workflow/pattern changes |
| `.claude/CODEBASE_MAP.md` | Codebase structure for AI context | After structural changes |
| `docs/SPEC.md` | Product specification | After major feature additions |

### Operations Docs
| File | Purpose | Update Frequency |
|------|---------|------------------|
| `DEPLOYMENT.md` | Deployment procedures | After infra changes |
| `docs/RUNBOOK.md` | Operations runbook | After ops procedures change |

### Developer Docs (docs/)
| File | Purpose | Update Frequency |
|------|---------|------------------|
| `docs/DEVELOPMENT_PATTERNS.md` | Coding patterns & conventions | After new patterns established |
| `docs/PRD_PRODUCTION_DEPLOYMENT.md` | Production deployment PRD | Rarely |
| `docs/prds/*.md` | Product requirement docs | Per feature |
| `docs/adr/*.md` | Architecture decision records | Per decision |
| `docs/patterns/*.md` | Specific pattern documentation | As needed |

---

## When to Update

| Trigger | Docs to Update |
|---------|---------------|
| New feature added | README, CODEBASE_MAP, possibly SPEC |
| New route/blueprint | CODEBASE_MAP |
| New model | CODEBASE_MAP |
| New pattern established | DEVELOPMENT_PATTERNS, CODEBASE_MAP |
| Setup process changed | README, DEPLOYMENT |
| Infrastructure changed | DEPLOYMENT, RUNBOOK |
| Ops procedure changed | RUNBOOK |
| AI workflow changed | CLAUDE.md |
| Architecture decision | Create new ADR in docs/adr/ |

---

## Invocation

**Update specific doc:**
```
/update-docs readme
/update-docs map
/update-docs patterns
```

**Update after feature work:**
```
/update-docs feature [feature-name]
```

**Full documentation refresh:**
```
/update-docs full
```

---

## Execution Steps

### Quick Update (Single Doc)

1. **Read the current doc**
2. **Identify what changed** - git diff, recent work
3. **Edit the relevant sections**
4. **Update any "Last Updated" dates**

### Feature Update

After completing a feature, update these docs:

1. **CODEBASE_MAP.md**
   - Add new routes to Route Patterns table
   - Add new models to Key Models section
   - Add entry to Recent Changes table

2. **README.md** (if user-facing)
   - Add to Features list if significant
   - Update setup if new dependencies
   - Update usage examples if needed

3. **docs/SPEC.md** (if major feature)
   - Add to feature list
   - Document user-facing behavior

### Full Refresh

1. **Run exploration:**
   ```
   Use Task tool with Explore agent for:
   - Current directory structure
   - All models and relationships
   - All routes and blueprints
   - Key patterns in use
   ```

2. **Update each doc in order:**
   - CODEBASE_MAP.md (structure, models, routes)
   - README.md (features, setup, usage)
   - DEVELOPMENT_PATTERNS.md (patterns, conventions)
   - CLAUDE.md (if workflows changed)

3. **Verify all docs are consistent**

---

## Doc-Specific Guidelines

### README.md
```markdown
# Project Name

## Overview
[What it does, who it's for]

## Features
[Bullet list of main features]

## Quick Start
[Minimal setup steps]

## Development
[Local dev setup]

## Testing
[How to run tests]

## Deployment
[Link to DEPLOYMENT.md or brief summary]

## License
[License info]
```

**Keep it:**
- Scannable (headers, bullets)
- Focused on getting started
- Links to detailed docs rather than duplicating

### CODEBASE_MAP.md
```markdown
# Codebase Map

> Last Updated: YYYY-MM-DD

## Overview
## Directory Structure
## Key Models
## Route Patterns
## Architecture Patterns
## Quick Reference
## Recent Changes
```

**Keep it:**
- Under 500 lines
- Navigation-focused ("where do I find X?")
- Tables over prose
- Updated incrementally

### CLAUDE.md
```markdown
# Project Instructions

## Communication Style
## Safety Rules
## Local Development
## Multi-User Data Isolation
## Testing
## Code Style
## Do NOT
```

**Keep it:**
- Focused on what AI needs to know
- Rules and constraints prominent
- Specific to this project

### DEVELOPMENT_PATTERNS.md
```markdown
# Development Patterns

## Live Search Pattern
## Form Validation
## AJAX Partials
## Error Handling
## Testing Patterns
```

**Keep it:**
- Code examples for each pattern
- When to use each pattern
- Common mistakes to avoid

### ADRs (docs/adr/)
```markdown
# ADR-XXX: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
[Why this decision was needed]

## Decision
[What we decided]

## Consequences
[What this means going forward]
```

**Create new ADR when:**
- Choosing between technologies
- Establishing new patterns
- Making breaking changes
- Changing architecture

---

## Verification Checklist

After updating docs:

- [ ] All file paths mentioned exist
- [ ] All commands listed actually work
- [ ] Model names match models.py
- [ ] Route prefixes match app.py
- [ ] No outdated feature references
- [ ] Dates updated where applicable
- [ ] Consistent terminology across docs

---

## Example: After Adding "Social Posting" Feature

**CODEBASE_MAP.md changes:**
```markdown
## Route Patterns
| `/social` | social | Social media posting |  <!-- ADD -->

## Key Models
| `SocialConnection` | Platform OAuth tokens | `platform`, `user_id` |  <!-- ADD -->
| `ScheduledPost` | Queued posts | `content`, `scheduled_for` |  <!-- ADD -->

## Recent Changes
| 2026-01-18 | Added social media posting (Twitter/X) |  <!-- ADD -->
```

**README.md changes:**
```markdown
## Features
- Social media posting with scheduling  <!-- ADD -->
```

**docs/SPEC.md changes:**
```markdown
## Social Media Integration
- Connect Twitter/X accounts
- Generate posts from episode content
- Schedule posts for optimal times
```

---

## Related Files

- `.claude/CODEBASE_MAP.md` - Codebase structure
- `.claude/prompts/update-docs.md` - This file
- `README.md` - Project readme
- `CLAUDE.md` - AI instructions
- `docs/` - Detailed documentation
