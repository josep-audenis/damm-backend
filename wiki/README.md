# SmartTruck Wiki Operating Rules

This wiki follows the LLM-wiki pattern from Andrej Karpathy's gist: keep raw sources immutable, maintain a persistent markdown wiki, and use schema/instruction files to keep agents disciplined across sessions.

The frontend and backend teams will code in separate repos. The wiki will **not** live-sync between repos. Treat this folder as the shared contract snapshot that each repo should copy at the start of work.

## Layers

### 1. Raw Sources

Raw sources are immutable. Agents may read them but must not rewrite them.

Examples:

- Hackathon challenge brief.
- Damm decks.
- Excel workbooks.
- Photos.
- External docs.
- Original plan files.

### 2. Wiki

The wiki is the maintained markdown layer. Agents can update wiki pages when they learn something useful, but contract changes must be explicit.

Core pages:

- [index.md](index.md)
- [log.md](log.md)
- [contracts/data-models.md](contracts/data-models.md)
- [contracts/api-contract.md](contracts/api-contract.md)
- [contracts/separation-of-concerns.md](contracts/separation-of-concerns.md)
- [backend/agent-instructions.md](backend/agent-instructions.md)
- [frontend/agent-instructions.md](frontend/agent-instructions.md)

### 3. Schema / Agent Rules

Each repo has a `CLAUDE.md` file. It points agents to this wiki and tells them how to work safely.

Repo-specific files:

- `BACKEND_CLAUDE.md`
- `FRONTEND_CLAUDE.md`

When copied into a repo, rename the relevant one to:

```txt
CLAUDE.md
```

## Non-Live-Sync Rule

Because backend and frontend repos will not share live wiki updates:

1. Treat `wiki/contracts/*` as the source of truth at the start of a work session.
2. If a contract must change, update the local wiki and add a log entry.
3. Also create a clear `CONTRACT_CHANGE_PROPOSAL` entry in the final message or PR notes.
4. Do not silently change API field names, enum values, WebSocket message types, or endpoint paths.
5. Frontend may mock data only if it matches the contract.
6. Backend may add fields, but must not remove or rename contracted fields without an explicit proposal.

## Contract Stability Priority

The most important contract is:

- Pydantic domain models.
- Request/response schemas.
- WebSocket message protocol.
- Endpoint paths.
- Enum values.

Implementation details may evolve. The contract must remain stable unless both repos intentionally update.

