# Chat With Tafseer

This service exposes Quran tafsir content through FastAPI.

## Tafsir Source

The current tafsir endpoints use the public read-only Quran API at `https://api.quran.com/api/v4`.
They do not require a Quran access token or client ID.

## Run

```bash
uv run uvicorn main:app --reload
```

## Tafsir Example

```bash
curl http://127.0.0.1:8000/tafseer/169/chapter/1
```

## Chat Example

`POST /chat` requires an explicit tafsir resource and verse key.

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": 169,
    "verse_key": "1:1",
    "message": "What does it say?",
    "thread_id": "session-1"
  }'
```

Successful responses include:

```json
{
  "answer": "string",
  "resource_id": 169,
  "verse_key": "1:1",
  "chapter_number": 1
}
```
