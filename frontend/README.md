# Core Gateway frontend

A small React + Vite request builder for trying out the Core API Gateway: pick a method, enter an
endpoint and API key, send the request, and inspect the response and timing.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build into dist/
npm run lint
```

The gateway URL defaults to `http://127.0.0.1:8000`. To change it, copy `.env.example` to
`.env.local` and set `VITE_API_BASE`.

API keys are held in memory only and are never saved to history or browser storage.
