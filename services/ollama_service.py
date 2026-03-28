from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os

load_dotenv()

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

llm = ChatOllama(model="gemma3:4b-cloud", 
                 base_url="https://ollama.com",
                 client_kwargs={"headers": {"Authorization": f"Bearer {OLLAMA_API_KEY}"}})