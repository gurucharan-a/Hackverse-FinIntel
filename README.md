# FinIntel (PS-01)

Multi-agent retail investment intelligence: live-style tape + filing RAG + profile-aware synthesis, with a visible reasoning chain.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for agent contracts, demo script, metrics, and degraded-data rules.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
npm --prefix frontend install && npm --prefix frontend run build
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000
