import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import MODEL_NAME

logger = logging.getLogger(__name__)

PLACEHOLDERS = {
    "your-google-api-key-here",
    "placeholder",
    "your_google_api_key",
    "your-gemini-api-key-here",
    "your_gemini_api_key",
    ""
}

def get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Returns a ChatGoogleGenerativeAI LLM instance configured with GOOGLE_API_KEY from streamlit secrets file or environment variable."""
    api_key = None
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key or str(api_key).strip().lower() in PLACEHOLDERS:
        raise ValueError(
            "Google API key is missing or still set to the placeholder in .streamlit/secrets.toml (GOOGLE_API_KEY). "
            "Please replace it with your real Google Gemini API key."
        )

    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=temperature,
        google_api_key=api_key
    )
