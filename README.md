# Chat With Tafseer

This service exposes Quran tafsir content through FastAPI.

## Tafsir Source

The current tafsir endpoint uses the public read-only Quran API at `https://api.quran.com/api/v4`.
It does not require a Quran access token or client ID for `GET /tafseer/{resource_id}/chapter/{chapter_number}`.

The older `QURAN_API_ACCESS_TOKEN` and `QURAN_API_CLIENT_ID` values in `.env` are obsolete for this endpoint.
Other unrelated environment variables can remain as they are.

## Run

```bash
uvicorn main:app --reload
```

## Example

```bash
curl http://127.0.0.1:8000/tafseer/169/chapter/1
```
