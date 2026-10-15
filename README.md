# Analizator umów

Aplikacja do analizy umów (FastAPI + React + PostgreSQL). Wszystkie dane w repozytorium są syntetyczne.

## Uruchomienie

```bash
cp .env.example .env   # uzupełnij ANTHROPIC_API_KEY i hasła
docker compose up -d --build
curl localhost:8080/api/health   # {"status":"ok"}
```

Frontend: http://localhost:8080, backend: http://localhost:8000.
