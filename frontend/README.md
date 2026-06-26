# VERA Operations Dashboard (frontend)

Next.js 16 (App Router) + TypeScript + Tailwind v4 dashboard for monitoring
the VERA bot in real time. See the [repo-level README](../README.md) for
full project context, architecture, and the backend it talks to.

## Setup

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_BOT_URL if not http://localhost:8080
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend
(`../backend`) must be running for any page to show real data — every page
fails gracefully with a clear connection-error state if it isn't.

## Pages

- **`/`** — live ops overview: heartbeat-pulse status indicator, datastore
  connectivity, context counts, action/CTA distribution, recent actions feed.
- **`/conversations`** — turn-by-turn conversation timelines pulled from
  `/v1/dashboard/replies`, with auto-reply badges and "switched to ACTION
  mode" intent-transition markers.
- **`/contexts`** — searchable inspector over every context currently loaded
  in the bot, by scope, with full JSON payload viewing.
- **`/simulator`** — run health checks and `/v1/tick` calls against the live
  bot directly from the browser, with streamed log output. This complements
  (does not replace) the official `judge_simulator.py`, which is the only
  thing that produces real LLM-judged scores.
- **`/scores`** — objective anti-pattern tracking (URL violations, taboo
  vocabulary hits, missing required fields, numeric-specificity proxy) computed
  client-side from the bot's own logged actions.

## Build

```bash
npm run build && npm run start
```

Production builds use `output: "standalone"` (see `next.config.ts`) for a
minimal Docker image — see `Dockerfile` and the root `docker-compose.yml`.

`NEXT_PUBLIC_BOT_URL` is inlined into the client bundle at **build** time.
If you rebuild against a different backend URL, you must rebuild the app
(or the Docker image with a different `--build-arg NEXT_PUBLIC_BOT_URL=...`).

## Design

Dark navy/electric-blue ops-tool palette (`app/globals.css`, CSS custom
properties prefixed `--vera-*`), Inter for UI text, JetBrains Mono for
JSON/context IDs/code. The signature visual is the `PulseMonitor` component
— an animated ECG-style trace representing VERA's "the living heartbeat of
merchant engagement" framing from the original design brief, rather than a
generic spinner.
