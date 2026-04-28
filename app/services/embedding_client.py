import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
)

def get_embedding(text: str) -> list[float]:
    response = _client.embeddings.create(
        model="text-embedding-v4",
        input=text,
        dimensions=1024,
        encoding_format="float"
    )
    return response.data[0].embedding

def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = _client.embeddings.create(
        model="text-embedding-v4",
        input=texts,
        dimensions=1024,
        encoding_format="float"
    )
    return [item.embedding for item in response.data]