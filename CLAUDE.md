# Damm Smart Truck — Wiki & Agent Conventions

This repo uses an LLM-maintained wiki pattern. Three layers:

- **Database** — `data/app_db.json` is the runtime source of truth for the demo app.
- **Wiki** — LLM-generated `.md` files in `wiki/` directory. LLM owns and maintains.
- **Schema** — this file (CLAUDE.md). Defines conventions and workflows for agents.

---

## Wiki Structure

Organized by topic. See [wiki/index.md](wiki/index.md) for full catalog.

Categories: Meta, Contracts, Technical, Data, Planning, Backend, Frontend, Decisions.

---

## Agent Workflows

### On Ingest (new data source added)

1. Read source → extract key points
2. Write or update relevant wiki page(s)
3. Update [wiki/index.md](wiki/index.md) if new page
4. Append entry to [wiki/log.md](wiki/log.md)

### On Query (user asks a question)

1. Read [wiki/index.md](wiki/index.md) → find relevant pages
2. Drill into pages, synthesize answer
3. Optionally file answer as new wiki page if valuable synthesis
4. Append query entry to [wiki/log.md](wiki/log.md)

### On Lint (periodic maintenance)

Check for:
- Contradictions between pages
- Stale claims (outdated by recent changes)
- Orphan pages (no inbound links)
- Missing cross-references
- Gaps in coverage

---

## Wiki Conventions

**Page format:**
- Every page: `# Title` at top
- Optional YAML frontmatter: `tags`, `sources`, `updated`
- Cross-references: markdown links `[text](path.md)`

**Log format:**
```
## [YYYY-MM-DD] <type> | <title>

Brief description. One paragraph.
```

Types: `ingest`, `query`, `lint`, `update`

---

## Content Boundaries

- **Wiki owns:** domain knowledge, context, decisions, constraints, specifications
- **Code owns:** implementation, file paths, actual behavior
- **This file owns:** agent instructions only (how to maintain the wiki)

Do NOT put:
- Solution code or algorithms in CLAUDE.md (move to wiki pages)
- Specific project context (move to wiki pages)
- Architectural decisions (move to wiki/decisions/)

---

## When Unsure

- Domain vocab → wiki/data/db-schema.md
- Tech decisions → wiki/technical/ or wiki/decisions/
- Data structure → wiki/contracts/
- Timeline/scope → wiki/planning/
- Implementation rules → wiki/backend/ or wiki/frontend/
