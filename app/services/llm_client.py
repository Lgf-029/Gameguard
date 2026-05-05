import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm(temperature=0.2, model="deepseek-v4-pro"):
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("DEEPSEEK_BASE_URL"),
        max_tokens=512
    )