# InsiderBrief Deployment

## Stack

| Component | Platform | URL |
|---|---|---|
| **Frontend** | Cloudflare Pages | `https://agastya.pages.dev` |
| **Backend** | Railway | `https://agastya-production.up.railway.app` |

---

## Frontend (Cloudflare Pages)

Redeploy after any frontend changes:

```bash
source ~/.nvm/nvm.sh
cd web && npm run build && npx wrangler pages deploy dist --project-name agastya
```

---

## Backend (Railway)

Redeploy after any backend changes:

```bash
source ~/.nvm/nvm.sh
railway up --detach
```

### Environment variables (already set)

```
CRUSTDATA_API_KEY  — set via `railway variables set`
OPENAI_API_KEY     — set via `railway variables set`
```

### Useful commands

```bash
railway logs           # view live logs
railway service status # check deployment status
railway variables      # list env vars
```

---

## Connecting frontend → backend

The frontend API client should point to the Railway backend URL.

In `web/.env`:
```env
VITE_API_BASE_URL=https://agastya-production.up.railway.app
```

CORS is already configured in `app/main.py` to allow `https://agastya.pages.dev`.
