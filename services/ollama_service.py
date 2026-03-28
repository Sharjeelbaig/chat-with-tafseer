import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b-cloud")

client_kwargs = {}
if OLLAMA_API_KEY:
    client_kwargs["headers"] = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    client_kwargs=client_kwargs,
)
