# Frontend Deployment (Phase 5E.10)

The CareerPilot frontend is a standard Vite + React SPA. It is statically
hostable on any provider that can:

1. Serve the `dist/` build output over HTTPS, and
2. Fall back unknown paths to `index.html` (SPA routing).

No provider has been selected in this repository, so this document stays
generic. Do NOT claim a deployment has occurred — this documents the flow.

---

## Prerequisites (public configuration)

The production bundle needs two build-time environment values. **Both are
public** (Vite inlines them into the JS bundle that every visitor downloads):

| Variable | Required | Meaning |
|---|---|---|
| `VITE_API_BASE_URL` | **Yes (production build)** | HTTPS origin of the deployed backend, e.g. `https://api.careerpilot.app` |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID` | Yes, if Firebase auth is used | The public Firebase **client** config from the Firebase console |

```sh
# Production-style example — REPLACE with your own domains.
VITE_API_BASE_URL=https://api.careerpilot.app
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=careerpilot-96581.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=careerpilot-96581
VITE_FIREBASE_STORAGE_BUCKET=careerpilot-96581.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

### Secret policy

`VITE_*` values are **public** — they are compiled into the bundle and can be
read by anyone who visits the deployed site. Never place any of the following
in a `VITE_*` variable:

- Firebase Admin SDK / service-account credential (`.json`) contents
- OpenAI / Adzuna / Jooble / any provider API key intended to be secret
- Database connection strings
- JWT signing secrets
- Backend secret keys

Only the public Firebase **browser** configuration and the (public) API origin
belong in Vite environment variables. Local env files (`.env`, `.env.local`,
`.env.*.local`) are git-ignored and untracked.

## Production build validation

`vite.config.js` validates the environment during `vite build` (
`mode === 'production'`):

- **`VITE_API_BASE_URL` missing** → the build **fails** with a message naming
  the variable and an example value.
- **`VITE_API_BASE_URL` points at localhost / 127.0.0.1** → the build prints a
  loud warning and continues (so `npm run build && npm run preview` still works
  locally), but you are explicitly told the bundle is not production-ready.

The backend API **does not use an `/api` prefix**; routers live at the root
(`/jobs`, `/resumes`, `/applications`, `/analytics`, …). The frontend client
joins endpoint paths straight onto `VITE_API_BASE_URL` with exactly one slash,
and never appends `/api`, so **do not** set a base URL that includes a path.

## Local development (frontend only)

```sh
cd frontend
npm install

# Optional: a frontend/.env file (git-ignored), e.g.
#   VITE_API_BASE_URL=http://127.0.0.1:8000
#   + the six VITE_FIREBASE_* values

npm run dev        # http://localhost:5173, backend must be running on :8000
```

No dev proxy is configured or required — the client always calls the absolute
origin from `VITE_API_BASE_URL`. If unset, the client falls back to
`http://localhost:8000` for development.

## Production deployment flow

1. **Set `VITE_API_BASE_URL`** to the deployed HTTPS backend origin (no
   trailing slash, no path).
2. **Set the public Firebase browser config** (`VITE_FIREBASE_*`) to the values
   for the production Firebase project.
3. **Run `npm run build`** — the production build will fail fast if
   `VITE_API_BASE_URL` is missing.
4. **Publish `dist/`** to the static host.
5. **Configure SPA fallback** so all app routes resolve to `index.html`. The
   current React routes include `/home`, `/discover`, `/resumes`, `/pipeline`,
   `/insights`, `/profile`, `/settings`, plus aliases such as `/dashboard`,
   `/jobs`, `/applications`, and `/analytics`. Directly navigating to any of
   these must serve `index.html` (see SPA fallback below).
6. **Enable HTTPS** for the frontend origin (and the API origin).
7. **Configure backend CORS** to allow the frontend origin (see CORS below).
8. **Verify the production smoke flow** — see below.

### SPA fallback / static-routing note

The app uses `BrowserRouter`, so the browser requests real paths like
`https://app.example.com/resumes`. Your static host must fall back to
`index.html` for any path that is not a static asset:

- **Cloudflare Pages**: create a `_redirects` file with
  `/* /index.html 200` (or use the "Single-Page Application" setting).
- **Vercel**: `vercel.json` with `rewrites: [{ "source": "/(.*)",
  "destination": "/index.html" }]`.
- **Netlify**: a `_redirects` file with `/* /index.html 200` (or the SPA
  checkbox).
- **nginx**: `location / { try_files $uri $uri/ /index.html; }`

Because no provider is selected, no provider-specific file is committed. Asset
paths are emitted with Vite's default `base: '/'` and are intended for hosting
at the domain root (no subdirectory prefix).

### CORS alignment

The backend is a separate origin from the frontend. For the browser to accept
API responses:

- Deployed frontend origin: `https://app.example.com`
- Deployed backend origin: `https://api.example.com`
- **Backend** `CORS_ORIGINS` must explicitly contain the **frontend** origin:

```
ENVIRONMENT=production
CORS_ORIGINS=https://app.example.com
```

Phase 5E.1 already enforces: explicit production origins (no silent
localhost/wildcard fallback), no `*` wildcard, no credentials-with-wildcard.
HTTPS terminates at the hosting infrastructure (frontend) and at the API
reverse proxy; the app does not rewrite HTTP→HTTPS and must be served over
HTTPS in production.

### Production smoke flow

1. Open the frontend origin over HTTPS and confirm the landing/login page
   loads (HTTPS and assets OK).
2. Sign in with Firebase (confirms `VITE_FIREBASE_*` config works).
3. Trigger any authenticated list (e.g. `/resumes`) and confirm data loads —
   this confirms `VITE_API_BASE_URL` + backend CORS allow the frontend origin.
4. Directly open e.g. `https://app.example.com/resumes` in a fresh tab to
   confirm SPA fallback returns `index.html` (no 404).
5. Confirm the network tab shows API calls to the **HTTPS** API origin (no
   mixed-content).

## Build / checks

```sh
npm run build   # validated production build (see above)
npm run lint    # oxlint
npm test        # node contract checks (no framework needed)
npm run preview # serve dist/ locally to preview the production build
```