# HRRag

**How do I ask questions about our internal HR documents without sending them to a cloud?**

HRRag is a self-hosted conversational RAG (Retrieval-Augmented Generation) platform that lets employees query internal HR documents — policies, contracts, regulations, manuals — using plain natural language. Every component runs locally: the database, the embedding model, and the LLM. No document, query, or answer ever leaves your server.

---

## Screenshots

<details>
<summary>Login page (dark mode)</summary>

![Login page — dark mode](showroom/home_login_dark.png)

</details>

<details>
<summary>Chat — querying an HR document</summary>

![Chat interface with document retrieval](showroom/chat.png)

</details>

---

## What problem does it solve?

HR teams maintain large bodies of documents (labor contracts, internal regulations, benefits policies, onboarding guides) that employees struggle to search. Traditional keyword search fails when the question uses different vocabulary than the document. Sending documents to external AI APIs raises confidentiality concerns.

HRRag answers questions like:
- "How many vacation days do I get after my first year?"
- "What is the disciplinary process for repeated absences?"
- "Does the contract cover remote work expenses?"

…by finding the exact passage, showing the source and page number, and generating a grounded answer — all on-premise.

---

## Architecture

```
┌──────────────────────────────┐   ┌──────────────────────────────────────┐
│  Browser (React 19 + Vite)   │   │  MCP Clients                         │
│  • Chat UI + token streaming │   │  • Claude Code (stdio)               │
│  • Document upload           │   │  • mcphost + Ollama (streamable HTTP)│
│  • MCP token panel           │   │  • OpenAI / Anthropic API            │
│  • EN/ES i18n, dark/light    │   └──────────────┬───────────────────────┘
└──────────────┬───────────────┘                  │ POST /mcp/
               │ HTTP / SSE tokens                │ JSON-RPC 2.0
┌──────────────▼──────────────────────────────────▼───────────────────────┐
│  Backend (FastAPI + Python)                                              │
│                                                                          │
│  REST API                          MCP Server (FastMCP)                 │
│  • JWT auth (email-only)           • Mounted at /mcp/                   │
│  • Document ingestion pipeline     • 6 tools: search, get_chunk,        │
│  • Hybrid RAG retrieval            │           get_context, compare,    │
│  • Streaming LLM via Ollama        │           find_references,         │
│                                    │           list_documents           │
│  core/retrieval.py ────────────────┘ (shared retrieval pipeline)        │
└────────────┬──────────────────────────────────┬─────────────────────────┘
             │                                  │
┌────────────▼────────────┐         ┌───────────▼─────────────────────────┐
│  PostgreSQL 17           │         │  Ollama (host-native)               │
│  + pgvector              │         │  • qwen2.5:14b  (LLM)              │
│                          │         │  • nomic-embed-text (embeddings)    │
│  • users                 │         │    768 dims, asymmetric             │
│  • documents (+ doc_type)│         └─────────────────────────────────────┘
│  • document_chunks       │
│    parents: context      │
│    children: HNSW cosine │
│  • chat_sessions         │
│  • chat_messages         │
└──────────────────────────┘
```

All models run via **Ollama on the host** — no Docker container needed for inference. CPU inference works; a GPU significantly reduces response latency.

---

## Key processes

### 1. Document ingestion — parent-child chunking

When a document is uploaded, text extraction and embedding happen in an async background task (the HTTP response returns immediately):

```
Upload → Extract text (PDF / DOCX / TXT / MD)
       → Split into parent chunks (~2000 words, 100-word overlap)
       → Split each parent into child chunks (~400 words, 50-word overlap)
       → Embed children via nomic-embed-text (768-dim vectors)
       → Store in PostgreSQL — parents without embedding, children with HNSW index
```

**Why two levels?** Small children produce precise embeddings for retrieval; large parents give the LLM enough surrounding context to answer accurately. Without this, a 400-word chunk can lack the context needed to understand what the relevant sentence actually means.

### 2. Retrieval pipeline — HyDE + hybrid search

Every user question goes through a multi-step pipeline before reaching the LLM:

```
User question
  │
  ├─ HyDE: generate a hypothetical document excerpt (Ollama, temp 0.3)
  ├─ Query rewrite: generate 3 formal search variants (Ollama, temp 0.5)
  │   (both run in parallel)
  │
  ├─ Embed: [original query] + [HyDE] + [3 rewrites] → up to 5 vectors
  │         all prefixed "search_query:" (nomic asymmetric model requirement)
  │
  ├─ Vector search: parallel pgvector cosine search per vector → merge pool
  │   hit_count = how many searches returned this chunk
  │   best_vec_score = highest cosine similarity across all searches
  │
  ├─ Full-text search: tsvector 'simple' (language-agnostic) on all variants
  │
  ├─ Unified score: hit_norm×0.5 + vec_score×0.3 + fts_norm×0.2
  ├─ Dynamic threshold: mean − 1.5×std (floor at min_similarity×0.5)
  │
  └─ Fetch parent chunks → build context block → send to LLM
```

**Why HyDE?** Users ask in colloquial language ("how many days for a wedding?") but HR documents use formal vocabulary ("marriage leave entitlement"). HyDE generates a formal hypothesis that lands closer to the right passage in embedding space.

**Why hybrid?** Vector search handles synonyms and paraphrases; full-text handles exact terms (article numbers, codes, dates). The combination covers most HR document retrieval patterns without hardcoded vocabulary.

**Why the `search_query:` prefix?** `nomic-embed-text` is an asymmetric model trained with separate prefixes for queries and documents. Omitting the prefix on queries produces poor cosine similarity against document embeddings — this was the single biggest retrieval quality fix in this project.

### 3. Streaming answer generation

After retrieval, the LLM receives a prompt in the user's language (EN or ES) containing:
- A strict instruction to answer only from the provided excerpts
- The parent-chunk context blocks, labeled with source file and page number
- The last 3 turns of conversation history
- The current question

Tokens are streamed back via SSE as they are generated. On completion, source citations (document name, page, excerpt) are sent in a final `done` event and displayed below the answer.

---

## Why MCP gives better answers than a plain RAG chat

In the standard chat flow, the retrieval pipeline runs once per question and the LLM answers from whatever chunks it found. The LLM has no way to say "I need more context" or "let me check another document type" — it works with what retrieval gave it.

With MCP, the model drives the retrieval loop itself:

```
User: "Does my contract give me more vacation days than the law requires?"

Model thinks:
  1. I need to know what the law says       → calls search("vacaciones", doc_type="ley")
  2. I need to know what the contract says  → calls search("vacaciones", doc_type="contrato")
     — or just calls compare("vacaciones")  → gets both at once, grouped by doc_type

  3. The contract mentions "Art. 22 del reglamento"
     → calls find_references(chunk_id) to find that article
  4. Art. 22 is ambiguous without surrounding context
     → calls get_context(chunk_id) to read the previous and next clauses

  Model now has 4 targeted lookups. Answers with exact citations.
```

**Why the answers are more precise:**

| | Chat RAG | MCP |
|---|---|---|
| Who drives retrieval | Pipeline (fixed, one-shot) | The model (iterative, adaptive) |
| Searches per question | 1 hybrid search | As many as needed |
| Can filter by doc type | Only if hardcoded | Yes — per call |
| Can follow references | No | Yes — `find_references` + `get_context` |
| Can compare doc types | No | Yes — `compare` runs all in parallel |
| Context per result | ~2000-word parent chunk | Same, but model selects which to use |
| Failure mode | Retrieves wrong chunks silently | Model can retry with a different query |

The model treats the tools like a search engine it controls: it queries, reads the result, decides if it has enough, and queries again if not. A plain RAG pipeline cannot do this — it fires once and whatever comes back is what the LLM gets.

---

## MCP server — use HRRag as an AI tool

HRRag exposes its retrieval pipeline as a **Model Context Protocol (MCP) server**, so any MCP-compatible client (Claude Code, mcphost + Ollama, OpenAI Responses API) can call the RAG engine as a structured tool — without going through the chat UI.

The server is mounted at `POST /mcp/` on the same FastAPI process and supports two connection modes:

| Mode | How | When to use |
|---|---|---|
| **Streamable HTTP** | `http://localhost:8000/mcp/` | mcphost, remote APIs, multi-user |
| **stdio** | subprocess via `uv run mcp_server.py` | Claude Code, local single-user |

Available tools: `search`, `get_chunk`, `get_context`, `compare`, `find_references`, `list_documents`.

See [docs/mcp.md](docs/mcp.md) for the full reference — how it works, both connection examples, auth, and how to add new tools.

---

## Repository structure

```
HRRag/
├── Makefile                    ← all common commands (run from repo root)
├── README.md                   ← this file
├── .mcp.json                   ← Claude Code MCP config (stdio transport)
├── backend/
│   ├── docker-compose.yml      ← PostgreSQL + pgvector (only external dependency)
│   ├── .env.example            ← environment variable template
│   ├── mcp_server.py           ← stdio entry point (used by Claude Code)
│   ├── README.md               ← API reference, DB schema, pipelines, env vars
│   └── app/
│       ├── auth/               ← email-only JWT auth
│       ├── documents/          ← upload, ingestion, chunking, embedding
│       ├── chat/               ← sessions, messages, retrieval, streaming
│       ├── core/               ← config, DB engine, security, embeddings, retrieval
│       └── mcp/                ← MCP server, auth, schemas, tools
│           ├── server.py       ← FastMCP instance, lifespan, 6 tool registrations
│           ├── auth.py         ← JWT validation outside FastAPI dependency injection
│           ├── schemas.py      ← Pydantic output types for all tools
│           └── tools/          ← one module per tool
└── frontend/
    ├── README.md               ← stack, component map, i18n guide, SSE flow
    └── src/
        ├── pages/              ← LoginPage, ChatPage
        ├── components/         ← layout, chat, documents
        ├── store/              ← auth, chat, theme (Zustand)
        ├── hooks/              ← TanStack Query wrappers
        └── locales/en|es/      ← i18n strings
```

For deeper detail on each component, see the dedicated READMEs:

- [backend/README.md](backend/README.md) — API reference, DB schema, full pipeline internals, all environment variables
- [frontend/README.md](frontend/README.md) — component map, i18n guide, SSE streaming flow, state management
- [docs/mcp.md](docs/mcp.md) — MCP server: how it works, connection examples, auth, adding tools

---

## Quick start

**Requirements:** Docker, [Ollama](https://ollama.com), Node.js ≥ 20, [uv](https://docs.astral.sh/uv/).

### 1. Pull Ollama models

```bash
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

### 2. First-time setup

```bash
make setup
# Creates backend/.env from backend/.env.example and installs all dependencies.
# Edit backend/.env — at minimum set SECRET_KEY (min 32 chars).
```

### 3. Run services (three separate terminals)

```bash
make db        # PostgreSQL on port 5432 (Docker, background)
make backend   # FastAPI on :8000 — REST API + MCP server at /mcp/
make frontend  # React + Vite on :5173
```

```bash
make help      # list all available commands
```

| URL | Description |
|---|---|
| http://localhost:5173 | Web app |
| http://localhost:8000/docs | Swagger API explorer |
| http://localhost:8000/mcp/ | MCP server (Streamable HTTP) |

### 4. Connect an MCP client (optional)

```bash
make mcp-token                        # generate a JWT for MCP clients
make mcp-stdio MCP_USER=you@co.com   # launch stdio server for Claude Code
```

For mcphost + Ollama, set `~/.mcphost.json` — see [docs/mcp.md](docs/mcp.md).

---

## Environment variables

All variables live in `backend/.env` (copy from `backend/.env.example`).

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✓ | JWT signing key — min 32 characters |
| `OLLAMA_MODEL` | | LLM model name. Default: `qwen2.5:14b` |
| `OLLAMA_EMBEDDING_MODEL` | | Embedding model. Default: `nomic-embed-text` |
| `OLLAMA_BASE_URL` | | Default: `http://localhost:11434` |
| `POSTGRES_PASSWORD` | | Must match `docker-compose.yml`. Default: `hrrag` |

See [backend/README.md](backend/README.md) for the full variable reference.

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.
