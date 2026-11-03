# Core Gateway frontend

A small React + Vite client for trying out the Core API Gateway: register and log in, generate and
revoke API keys, send requests, and inspect the response and timing.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build into dist/
npm run lint
```

The gateway URL defaults to `http://127.0.0.1:8000`. To change it, copy `.env.example` to
`.env.local` and set `VITE_API_BASE`.

Login tokens and API keys are held in memory only and are never saved to history or browser storage.
