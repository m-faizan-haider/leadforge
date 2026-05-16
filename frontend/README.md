# LeadForge AI Frontend

Next.js frontend for LeadForge AI.

## Local Development

```bash
npm install
copy .env.example .env.local
npm run dev
```

Open http://localhost:3000.

For local backend development, keep:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Production Build Check

```bash
npm run lint
npm run build
```

Both commands should pass before deploying to Vercel.

## Deploy On Vercel

Use Vercel for the frontend.

Recommended settings:

- Framework Preset: `Next.js`
- Root Directory: `frontend`
- Install Command: `npm install`
- Build Command: `npm run build`
- Output Directory: leave default

Add this Vercel environment variable:

```env
NEXT_PUBLIC_API_URL=https://your-production-api-url
```

Important: do not use `http://127.0.0.1:8000` in production. A deployed browser cannot reach your laptop localhost backend.

## Backend CORS

After Vercel gives you a frontend URL, add it to the backend `ALLOWED_ORIGINS` value:

```env
ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

Then redeploy or restart the backend.
