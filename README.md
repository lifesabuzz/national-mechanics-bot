# National Mechanics Bot — Minimal Deployment
This bundle includes a FastAPI chatbot, pricing engine, and DigitalOcean App Platform config.

## Files
- `app_chat.py` — API with /chat
- `price_quote.py` — pricing engine (dual tax, gratuity, rental, bartender)
- `policies.yaml` — policy settings
- `index.html` — tiny browser UI
- `requirements.txt` — dependencies
- `.do/app.yaml` — DigitalOcean config

## Local run
```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
uvicorn app_chat:app --reload
```
Open http://127.0.0.1:8000
