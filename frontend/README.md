# BarnamehSaz Novin — Frontend

React + TypeScript + Vite, RTL, Persian-first UI. Phase 5 (UI/UX).

## Env

Copy `.env.example` → `.env` (dev). Browser code calls the same-origin
`/api/v1` prefix; Vite dev-server proxies it to `VITE_API_TARGET`
(default `http://127.0.0.1:8000`). No hardcoded `localhost` in browser code.

## Run

```
npm install
npm run dev        # http://localhost:5173
npm run typecheck  # tsc --noEmit
npm test           # vitest run
npm run build      # tsc && vite build → dist/
```

## Notes

- Tokens live in memory only (module-scoped in `src/lib/api.ts`). Not in
  `localStorage`/`sessionStorage`.
- Dates: ISO 8601 to/from API; Persian (Jalali) display in UI via `Intl`
  (`fa-IR-u-ca-persian`). Persian/Arabic digits normalized to ASCII for API
  inputs (`src/lib/digits.ts`).
- Design tokens in `src/styles/tokens.css`; RTL throughout.
- No new backend endpoints; consumes exactly the Phase 1–4 APIs already in
  `backend`.

## Scope (Phase 5)

Landing, login, forced password change, role dashboard, planning cycles,
resources & availability, offerings, submission wizard, shared-offering
approvals, preflight, solver run & results, run history & comparison,
audit timeline. Excel/PDF export UI surface is a placeholder — actual file
generation ships in Phase 6 (per prompt 09/10).
