# HRRag — Backend

FastAPI REST API for conversational HR document querying using semantic retrieval (RAG) over PostgreSQL + pgvector and streaming answers via Ollama.

---

## Project structure

```
backend/
├── main.py                         # FastAPI app, CORS, routers, lifespan
├── pyproject.toml                  # Dependencies (uv)
├── .env                            # Environment variables (not committed)
├── .env.example                    # Variable template
└── app/
    ├── core/                       # Shared infrastructure
    │   ├── config.py               # Settings via pydantic-settings (.env)
    │   ├── database.py             # SQLAlchemy engine, Base, init_db, get_db
    │   ├── security.py             # JWT (create/decode) + get_current_user dependency
    │   └── embeddings.py           # embed_text / embed_texts via Ollama /api/embed
    │
    ├── auth/                       # Email-only authentication
    │   ├── models.py               # User (email PK, created_at, last_login)
    │   ├── schemas.py              # LoginRequest, TokenResponse, UserResponse
    │   ├── service.py              # login_or_create → creates user or updates last_login
    │   └── router.py               # POST /auth/login  GET /auth/me
    │
    ├── documents/                  # Document management and indexing
    │   ├── models.py               # Document, DocumentChunk (embedding vector(768))
    │   ├── schemas.py              # DocumentResponse
    │   ├── service.py              # upload, _index_document (bg task), delete
    │   ├── router.py               # GET/POST/DELETE /hr/documents
    │   └── processors/             # Text extraction per format
    │       ├── pdf.py              # PyMuPDF — text per page + tables → Markdown
    │       ├── docx.py             # python-docx — concatenated paragraphs
    │       └── text.py             # UTF-8 decode
    │
    └── chat/                       # Conversational sessions and messages
        ├── models.py               # ChatSession, ChatMessage
        ├── schemas.py              # SessionResponse, MessageResponse, SourceChunk
        ├── prompts.py              # Prompt templates keyed by language (en / es)
        ├── service.py              # Session CRUD, _retrieve (hybrid RAG), stream_message
        └── router.py               # CRUD /hr/sessions + POST stream
```

### Layer responsibilities

| Layer | Owns | Does NOT own |
|---|---|---|
| `core/` | Config, DB engine, JWT, embeddings | Business logic |
| `*/models.py` | SQLAlchemy table definitions | Request/response validation |
| `*/schemas.py` | Pydantic request/response shapes | DB access |
| `*/service.py` | Business logic and DB access | HTTP, request validation |
| `*/router.py` | HTTP routes, FastAPI dependencies | Direct business logic |

---

## Database

PostgreSQL 17 with the `pgvector` extension. Tables are created automatically by `init_db()` on startup.

```
users
  email            VARCHAR  PK
  created_at       TIMESTAMPTZ
  last_login       TIMESTAMPTZ

documents
  id               VARCHAR  PK
  user_email       VARCHAR  FK → users.email  CASCADE DELETE
  filename         VARCHAR                    # on-disk name (uuid + ext)
  original_name    VARCHAR                    # original upload filename
  file_size        INTEGER
  mime_type        VARCHAR
  chunks_count     INTEGER  DEFAULT 0
  status           VARCHAR  DEFAULT 'pending' # pending | indexing | indexed | error
  created_at       TIMESTAMPTZ

document_chunks
  id               VARCHAR  PK               # {doc_id}_p0 / {doc_id}_c0
  document_id      VARCHAR  FK → documents.id  CASCADE DELETE
  parent_id        VARCHAR  NULLABLE          # NULL = parent chunk, set = child chunk
  user_email       VARCHAR                    # denormalized for fast filtering
  content          TEXT
  embedding        VECTOR(768)               # pgvector HNSW cosine index (children only)
  chunk_index      INTEGER
  page_number      INTEGER  NULLABLE
  created_at       TIMESTAMPTZ

chat_sessions
  id               VARCHAR  PK
  user_email       VARCHAR  FK → users.email  CASCADE DELETE
  title            VARCHAR  NULLABLE          # auto-set from first message
  created_at       TIMESTAMPTZ
  updated_at       TIMESTAMPTZ

chat_messages
  id               VARCHAR  PK
  session_id       VARCHAR  FK → chat_sessions.id  CASCADE DELETE
  role             VARCHAR                    # 'user' | 'assistant'
  content          TEXT
  sources          TEXT  NULLABLE             # JSON array of SourceChunk
  created_at       TIMESTAMPTZ
```

---

## Indexing pipeline

When a file is uploaded the heavy work runs in a **background task** — the HTTP response returns immediately with `status='indexing'`.

```
1. upload()
   ├── Validate type (mime + extension) and size (≤ MAX_FILE_SIZE_MB)
   ├── Save file to UPLOAD_DIR/{user_email}/{doc_id}{ext}
   ├── Insert Document with status='indexing'
   └── Schedule _index_document() as a BackgroundTask

2. _index_document()  [async, same event loop]
   ├── Extract text by format:
   │     .pdf  → processors/pdf.py    (PyMuPDF, tables → Markdown)
   │     .docx → processors/docx.py   (python-docx)
   │     .txt / .md → processors/text.py (UTF-8 decode)
   ├── _build_parent_child() → two-level chunking (see below)
   └── _store_chunks()  [batches of 32]
         ├── INSERT parents first (no embedding, parent_id=NULL)
         ├── embed_texts() → Ollama /api/embed → 768-dim vectors
         ├── INSERT children with embedding (parent_id=<parent id>)
         └── Update Document: status='indexed', chunks_count=N_children
```

### Parent-child chunking

The document text is split into **two levels of granularity**:

```
Full document text
│
├── Parent 0  (words 0 – 1999, overlap 100)       parent_id = NULL
│     ├── Child 0  (words 0 – 399, overlap 50)    parent_id = parent_0
│     ├── Child 1  (words 350 – 749)
│     ├── Child 2  (words 700 – 1099)
│     └── Child 3  (words 1050 – 1449)
│
├── Parent 1  (words 1900 – 3899)
│     ├── Child 4  (words 1900 – 2299)
│     └── ...
└── ...
```

| | Parents | Children |
|---|---|---|
| Size | ~2000 words | ~400 words |
| Overlap | 100 words | 50 words |
| Has embedding | ✗ | ✓ (768 dims) |
| Role in RAG | Full context for the LLM | Similarity search |
| `parent_id` | NULL | Parent chunk ID |

**Why two levels:**
- Small children → precise embeddings, better retrieval recall.
- Large parents → the LLM receives full surrounding context (~2000 words) without losing information that gives meaning to the relevant passage.
- Without this, a 400-word chunk may lack the context needed to produce an accurate answer.

**Deterministic IDs:**
```
parent: {doc_id}_p0,  {doc_id}_p1,  ...
child:  {doc_id}_c0,  {doc_id}_c1,  ...   (global index across all parents)
```

---

## Retrieval pipeline (RAG)

```
stream_message(session, content, db, lang)
  │
  ├─ 1. Save ChatMessage(role='user')
  │
  ├─ 2. _retrieve(content, user_email, db, lang)   ← hybrid search (see below)
  │
  ├─ 3. _build_prompt(question, context, history, lang)
  │       · System instruction (answer ONLY from provided excerpts)
  │       · Context: parent text labeled [Source: file.pdf, p. N]
  │       · History: last 6 messages (3 turns)
  │       · User question
  │
  ├─ 4. Stream from Ollama /api/generate
  │       data: {"type": "token", "token": "..."}
  │       data: {"type": "done",  "message_id": "...", "sources": [...]}
  │       data: {"type": "error", "error": "..."}
  │
  └─ 5. Save ChatMessage(role='assistant') with sources JSON
         Update session.title (if None) and session.updated_at
```

### Hybrid search

`_retrieve()` runs a multi-step pipeline before the LLM sees the context:

```
Step 1 — HyDE + query rewrite (parallel)
  · HyDE: generate a hypothetical document excerpt via Ollama (temp 0.3)
  · Rewrite: generate 3 formal search variants via Ollama (temp 0.5)

Step 2 — Embed all variants
  embed_texts([query] + hypotheses, is_query=True)
  → adds "search_query:" prefix (nomic-embed-text asymmetric model)
  → up to 5 vectors (768 dims each)

Step 3 — Vector search per vector (parallel pgvector cosine)
  SELECT ... 1 - (embedding <=> :vec) AS vec_score
  WHERE parent_id IS NOT NULL   ← children only
  LIMIT candidate_limit         ← max(N_RESULTS * 10, 50) per vector
  Merge: hit_count = searches that returned this chunk
         best_vec_score = highest cosine across all searches

Step 4 — Full-text search (tsvector 'simple', language-agnostic)
  Run FTS for query + all hypotheses/rewrites
  ts_rank_cd(to_tsvector('simple', content), websearch_to_tsquery('simple', q))
  Merge best FTS score per chunk

Step 5 — Unified scoring + dynamic threshold
  hit_norm  = hit_count / total_vectors        (0–1)
  fts_norm  = fts_raw / max(fts_raw)           (0–1)
  final     = hit_norm × 0.5 + vec_score × 0.3 + fts_norm × 0.2
  threshold = max(MIN_SIMILARITY × 0.5, mean − 1.5 × std)
  Keep:     final >= threshold OR hit_count >= 2 OR fts_norm > 0

Step 6 — Fetch parent chunks
  parent_ids = {child["parent_id"] for child in top_children}
  SELECT id, content FROM document_chunks WHERE id = ANY(:ids)
  Dedup by parent_id — one context block per parent
  → LLM receives parent text (~2000 words)
  → Sources shown to user contain the child excerpt (300 chars)
```

**Why HyDE?** Users ask in colloquial language ("days off for a wedding?") but documents use formal vocabulary ("marriage leave entitlement"). HyDE generates a formal hypothesis whose embedding lands closer to the right passage.

**Why hybrid?**

| Strategy | Strength | Weakness |
|---|---|---|
| Vector (pgvector) | Synonyms, paraphrases, semantic variations | Fails on exact codes, article numbers, dates |
| Full-text (tsvector) | Exact terms ("Art. 45"), codes, numbers | No semantic understanding |
| **Hybrid** | **Both** | Two query paths instead of one |

**Why `search_query:` prefix?** `nomic-embed-text` is an asymmetric model trained with separate prefixes for queries and documents. Omitting the prefix on queries produces poor cosine similarity against document embeddings — this was the single largest retrieval quality fix.

**Why `'simple'` tsvector config?** Using `'spanish'` or `'english'` would break queries in the other language. `'simple'` only lowercases — it works for both.

### Reranker — design decision

HRRag does **not use a reranker**. The hybrid score from Step 5 is the final ranking before passing context to the LLM.

A cross-encoder reranker would re-score the top-N candidates by evaluating each (query, chunk) pair with a second model. The quality gain is real, but the cost is high: added latency per candidate, an extra model dependency, and one more component that can fail.

For the bounded HR domain (internal policies, regulations, contracts), the hybrid pipeline on 400-word chunks delivers sufficient precision without that overhead.

**If you want to add one later:** the insertion point is between Step 5 and Step 6 of `_retrieve()` — reorder `top_children` by reranker score before fetching parents. No schema changes needed.

---

## API reference

Base URL: `http://localhost:8000`  
Authentication: `Authorization: Bearer <JWT>` on all routes except `/auth/login`.

### Auth

| Method | Route | Body | Response |
|---|---|---|---|
| POST | `/auth/login` | `{"email": "user@co.com"}` | `{"access_token": "...", "token_type": "bearer"}` |
| GET | `/auth/me` | — | `{"email": ..., "created_at": ..., "last_login": ...}` |

### Documents

| Method | Route | Body | Response |
|---|---|---|---|
| GET | `/hr/documents` | — | `DocumentResponse[]` |
| POST | `/hr/documents` | `form-data: file=<file>` | `DocumentResponse` (201) |
| DELETE | `/hr/documents/{doc_id}` | — | 204 |

**`DocumentResponse`**
```json
{
  "id": "uuid",
  "user_email": "user@co.com",
  "original_name": "vacation_policy.pdf",
  "file_size": 204800,
  "mime_type": "application/pdf",
  "chunks_count": 47,
  "status": "indexed",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Chat sessions

| Method | Route | Response |
|---|---|---|
| GET | `/hr/sessions` | `SessionResponse[]` |
| POST | `/hr/sessions` | `SessionResponse` (201) |
| GET | `/hr/sessions/{id}` | `SessionWithMessages` |
| DELETE | `/hr/sessions/{id}` | 204 |
| POST | `/hr/sessions/{id}/messages/stream` | SSE stream |

**`SessionResponse`**
```json
{
  "id": "uuid",
  "user_email": "user@co.com",
  "title": "How many vacation days do I have?",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:05:00Z"
}
```

**Stream request body** `POST /hr/sessions/{id}/messages/stream`
```json
{"content": "How many vacation days do I get?", "lang": "en"}
```

**SSE events**
```
data: {"type": "token",  "token": "According to Article"}
data: {"type": "token",  "token": " 59 of the regulations"}
data: {"type": "done",   "message_id": "uuid", "sources": [...]}
data: {"type": "error",  "error": "message"}
```

**`SourceChunk`** (inside `done` and in `MessageResponse.sources`)
```json
{
  "document_name": "internal_regulations.pdf",
  "chunk_index": 12,
  "excerpt": "...first 300 chars of the child chunk...",
  "page_number": 7
}
```

### Health

```
GET /health  →  {"status": "ok"}
```

---

## `core/` module

Everything cross-cutting lives here. No business module (`auth/`, `documents/`, `chat/`) imports from another business module — they all import only from `core/`.

### `core/config.py`

`Settings` via `pydantic-settings`. Loads variables from `.env` automatically.  
Always import as: `from app.core.config import settings`

### `core/database.py`

- `engine` — SQLAlchemy async engine for PostgreSQL
- `Base` — shared `DeclarativeBase` for all models
- `init_db()` — creates the `vector` extension and all tables on startup
- `get_db()` — FastAPI dependency that yields `AsyncSession`

### `core/security.py`

- `create_token(email)` → JWT signed with `SECRET_KEY`
- `decode_token(token)` → `dict | None`
- `get_current_user` → FastAPI dependency: validates JWT and returns `User`

### `core/embeddings.py`

- `embed_text(text, is_query)` → `list[float]` (async)
- `embed_texts(texts, is_query)` → `list[list[float]]` (async) — for batches
- Adds `"search_query: "` prefix when `is_query=True` (asymmetric model requirement)
- Truncates to 75% of words on Ollama 400 context-length errors and retries

Calls `POST {OLLAMA_BASE_URL}/api/embed` with `OLLAMA_EMBEDDING_MODEL`.

---

## Environment variables

Defined in `.env` (copy from `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | **Required.** JWT signing key — min 32 characters |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_DAYS` | `7` | JWT lifetime |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `hrrag` | Database name |
| `POSTGRES_USER` | `hrrag` | Database user |
| `POSTGRES_PASSWORD` | `hrrag` | Database password |
| `EMBEDDING_DIM` | `768` | Vector dimension (must match the embedding model) |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `N_RESULTS` | `6` | Chunks to retrieve per query |
| `MIN_SIMILARITY` | `0.45` | Minimum cosine similarity threshold [0–1] |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama URL |
| `OLLAMA_MODEL` | `qwen2.5:14b` | LLM model |
| `OLLAMA_TEMPERATURE` | `0.1` | LLM temperature |
| `OLLAMA_TIMEOUT` | `120` | Ollama request timeout in seconds |
| `UPLOAD_DIR` | `./storage/uploads` | Uploaded file storage directory |
| `MAX_FILE_SIZE_MB` | `50` | Maximum file size per upload |

---

## Local development

```bash
# Start PostgreSQL
docker compose up -d postgres

# Install dependencies
uv sync

# Copy and edit environment variables
cp .env.example .env
# edit .env — set SECRET_KEY before starting

# Start in development mode
uv run uvicorn main:app --reload --port 8000
```

Interactive API docs:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Pipeline logs

The backend emits structured logs at each step:

```
INFO  app.core.embeddings   [EMBED] 5 texts is_query=True dim=768
INFO  app.chat.service      [HYDE] query='days off for a wedding'  lang=en  variants=4
INFO  app.chat.service      [FTS] queries=5  unique_hits=23
INFO  app.chat.service      [THRESHOLD] mean=0.312 std=0.089 dyn=0.178
INFO  app.chat.service      [RETRIEVAL] query='days off...'  user=u@co.com  top=6
INFO  app.documents.service [INDEX] doc=abc123  chunks=47
```
