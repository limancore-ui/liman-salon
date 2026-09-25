# Liman Salon — Public frontend

React + TypeScript + Vite app for the public salon experience (Foundation 1.0).

## Prerequisites

- Node.js 20+
- Backend API running locally on `http://127.0.0.1:8000`

## Development

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/s/{slug}` (replace `{slug}` with a salon slug from your backend data).

### API proxy

During `npm run dev`, Vite proxies `/api` to `http://127.0.0.1:8000`. The frontend calls relative URLs such as `/api/v1/public/salons/{slug}` so no CORS setup is required in local dev.

Production builds expect the same `/api` prefix to be served by your reverse proxy or hosting layer.

## Scripts

| Command        | Description                          |
|----------------|--------------------------------------|
| `npm run dev`  | Start dev server with API proxy      |
| `npm run build`| Typecheck (`tsc -b`) + production build |
| `npm run preview` | Preview production build          |

## Scope (Foundation 1.0)

- Public salon page at `/s/:slug`
- Salon header (name) and service list (name, description, duration, price)
- No booking, staff picker, availability, auth, or admin UI
