# HRRag — Frontend

React 19 + Vite + TypeScript single-page application for the HRRag conversational HR document platform.

---

## Tech stack

| Layer | Library / Tool |
|---|---|
| Framework | React 19 + Vite 6 |
| Language | TypeScript 5 (strict) |
| Styling | Tailwind CSS v4 + shadcn/ui |
| State | Zustand (auth, chat, theme) |
| Server state | TanStack Query v5 |
| Routing | React Router v7 |
| i18n | react-i18next (en / es) |
| HTTP | Axios (`/lib/api.ts`) |
| Icons | Lucide React |

---

## Project structure

```
frontend/
├── index.html                  # Entry point — page title, favicon
├── vite.config.ts              # Dev proxy /api → :8000, /hr → :8000
├── src/
│   ├── main.tsx                # App bootstrap, i18n + React init
│   ├── App.tsx                 # Router: /login, /dashboard, /sessions/:id
│   │
│   ├── i18n/
│   │   └── config.ts           # i18next setup — LanguageDetector, localStorage key
│   │
│   ├── locales/
│   │   ├── en/                 # English strings
│   │   │   ├── auth.json       # Login page
│   │   │   ├── chat.json       # Chat UI, sessions, input hints
│   │   │   ├── common.json     # Shared labels (logout, delete, theme, language)
│   │   │   └── documents.json  # Document list and upload
│   │   └── es/                 # Spanish strings (same keys)
│   │
│   ├── store/
│   │   ├── authStore.ts        # email, token, setAuth, logout (zustand + persist)
│   │   ├── chatStore.ts        # activeSessionId, isStreaming
│   │   └── themeStore.ts       # dark/light toggle (persisted in localStorage)
│   │
│   ├── hooks/
│   │   ├── useChat.ts          # useChatSessions, useChatSession, useCreateSession,
│   │   │                       # useDeleteSession — TanStack Query wrappers
│   │   └── useDocuments.ts     # useDocuments, useUploadDocument, useDeleteDocument
│   │
│   ├── lib/
│   │   ├── api.ts              # Axios instance — base URL + auth interceptor
│   │   └── utils.ts            # cn() (clsx + tailwind-merge)
│   │
│   ├── pages/
│   │   ├── LoginPage.tsx       # Email-only login, language + theme switchers
│   │   └── ChatPage.tsx        # Renders ChatWindow or welcome placeholder
│   │
│   └── components/
│       ├── layout/
│       │   ├── AppLayout.tsx        # Sidebar + main content shell
│       │   ├── Sidebar.tsx          # Document list, session list, new session button
│       │   ├── LanguageSwitcher.tsx # Globe dropdown — switches i18n language
│       │   └── ThemeToggle.tsx      # Sun/Moon button — switches dark/light
│       │
│       ├── chat/
│       │   ├── ChatWindow.tsx  # Session view: message list + streaming
│       │   ├── ChatInput.tsx   # Textarea with auto-resize, Enter to send
│       │   └── ChatMessage.tsx # Renders user/assistant bubbles + sources
│       │
│       └── documents/
│           ├── DocumentList.tsx    # List with status icons (indexed/indexing/error)
│           └── DocumentUpload.tsx  # Drag-and-drop + click-to-upload area
```

---

## Internationalization (i18n)

Language is auto-detected from the browser, then stored in `localStorage` under the key `docsrag-language`. Supported languages: **English** (`en`) and **Spanish** (`es`).

The language switcher is available both on the **login page** (top-right corner) and inside the **app** (sidebar footer). Switching language takes effect immediately with no page reload.

The active language is sent to the backend on every chat message as `{ content, lang }` — the backend uses it to select prompt templates, HyDE prompts, and query-rewrite prompts in the same language.

To add a new language:
1. Create `src/locales/<code>/` and copy all JSON files from `en/`.
2. Add the language code to `src/i18n/config.ts`.
3. Add the language option to `LanguageSwitcher.tsx` and both `common.json` files.

---

## State management

### `authStore`
Persisted to `localStorage`. Holds `email` and `token` (JWT). `logout()` clears both and redirects to `/login`.

### `chatStore`
Session memory: `activeSessionId` (currently displayed session) and `isStreaming` (disables input while a stream is in flight).

### `themeStore`
Persisted to `localStorage`. Toggles `dark` / `light`. Applied via a class on `<html>`.

---

## SSE streaming flow

When the user sends a message, `ChatWindow` opens a native `fetch` stream (not Axios — browsers don't support streaming responses with Axios):

```
POST /hr/sessions/{id}/messages/stream
Body: { content: string, lang: "en" | "es" }

SSE events received:
  data: {"type": "token",  "token": "..."}   → appended to streamingText state
  data: {"type": "done",   "message_id": "...", "sources": [...]}  → invalidates query cache
  data: {"type": "error",  "error": "..."}   → logged, streaming ends
```

On `done`, TanStack Query invalidates `['session', sessionId]` and `['sessions']` so the sidebar title and message list refresh without a page reload.

---

## API proxy (dev)

`vite.config.ts` proxies these prefixes to the backend to avoid CORS in development:

```
/api/*  → http://localhost:8000
/hr/*   → http://localhost:8000
/auth/* → http://localhost:8000
```

In production, point `VITE_API_BASE_URL` to the backend host.

---

## Development

```bash
# Install dependencies
pnpm install

# Start dev server (port 5173)
pnpm dev

# Type-check
pnpm tsc --noEmit

# Build for production
pnpm build
```

Or from the repo root:

```bash
make frontend
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL (used in production builds) |

In dev, the Vite proxy handles routing — `VITE_API_BASE_URL` is only needed when deploying a built bundle.
