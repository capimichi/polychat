# Polychat
Gateway FastAPI/CLI che espone un'unica interfaccia per più provider LLM (Perplexity, GPT, Kimi, DeepSeek). Fornisce API HTTP, CLI e session storage locale per sperimentare o integrare chatbot multi-provider senza dover gestire client e login separati.

## Caratteristiche
- API FastAPI montata su `polychat.api` con router dedicati per ogni provider sotto `/<provider>/chats`.
- CLI (`polychat.cli`) per login Perplexity e invio messaggi da terminale.
- Contenitore di dipendenze centralizzato e client per ciascun servizio, con test unitari e di integrazione.
- Pronto per Docker: `docker compose up --build` espone l'API su `0.0.0.0:8459` e mappa `./var` per le sessioni.

## Requisiti
- Python 3.11
- Dipendenze da installare con `pip install -r requirements.txt -r requirements-dev.txt`

## Avvio rapido
- API locale: `python -m polychat.api` (usa variabili da `.env`, default host `0.0.0.0`, port `8459`).
- CLI Perplexity login: `python -m polychat.cli perplexity:login`.

## Testing
Esegui l'intera suite con:
```bash
pytest
```
