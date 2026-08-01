# InfraPilot — frontend

Next.js 16 (App Router, Turbopack) + React Flow + Framer Motion. Renders the
city graph, the agent's live reasoning stream, and the approval flow.

See the [root README](../README.md) for the product, the integrations, and the
demo script.

## Development server

The backend must be running first — this app is a pure client of the FastAPI
service and has no data of its own.

```bash
# terminal 1, from repo root
cd backend && python -m uvicorn app.main:app --port 8000

# terminal 2
cd frontend
npm install
npm run dev          # http://localhost:3000
```

```bash
npm run build && npm start   # production build; faster, no HMR overhead
npx tsc --noEmit             # typecheck
npx playwright test          # E2E — this is the demo rehearsal
```

`NEXT_PUBLIC_API_BASE` overrides the API origin (default
`http://127.0.0.1:8000`). Never put a secret in a `NEXT_PUBLIC_*` variable —
those are inlined into the client bundle and shipped to the browser. This app
needs no credentials.

## Layout

```
app/
  page.tsx          Dashboard (the landing route)
  city/             The graph. Deep links: ?simulation= ?asset= ?rec=
  assets/ approvals/ risks/ simulations/ health/
components/
  AppShell.tsx      Sidebar, PageHeader, clickable Card, CardRow
  graph/            React Flow canvas and the custom asset node
  ReasoningStream   Live agent trace, throttled for readability
  KillChain         Attack path as numbered hops
  OspreyComparison  Same-severity, different-consequence panel
lib/
  api.ts            Typed fetch client
  types.ts          Mirrors backend/app/models.py
  useSimulation.ts  POST + SSE subscribe + display throttle
e2e/demo.spec.ts    The demo rehearsal
```

## Two Next.js 16 things that cost real debugging time

Both are pinned in `next.config.ts`; don't remove them without reading this.

**`allowedDevOrigins`.** Next 16 blocks cross-origin dev resources by default.
The dev server binds as `localhost`, so loading the app via `127.0.0.1` silently
blocks HMR and **the page never hydrates** — it renders, clicks land, and
nothing happens, with no error anywhere.

**`turbopack.root`.** This project sits inside a home directory that has its own
`package-lock.json`. Without pinning the root, Turbopack walks up, picks
`C:\Users\<user>` as the workspace root, and dev-mode CSS and font chunks 500.

## Conventions

- Design tokens are CSS variables in `app/globals.css` (`--ip-blue`, `--ip-red`,
  …). Use `text-[var(--ip-red)]`, not a raw hex.
- React Flow's stylesheet is imported in `globals.css` rather than in a
  component, so the control-room overrides reliably win the cascade.
- The frontend computes nothing. Every number on screen comes from the API; if a
  figure looks wrong, fix the engine, not the component.
- Cards that navigate use the router rather than wrapping children in a link —
  several contain their own clickable rows, and nesting interactive elements
  inside an anchor swallows the inner click.
