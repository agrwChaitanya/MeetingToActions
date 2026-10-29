import logging
from langchain_groq import ChatGroq
from src.config import MODEL_NAME

logger = logging.getLogger(__name__)

PLACEHOLDERS = {"your-groq-api-key-here", "placeholder", "your_groq_api_key", ""}

def get_llm(temperature: float = 0.0) -> ChatGroq:
    """Returns a ChatGroq LLM instance configured with GROQ_API_KEY from streamlit secrets file only."""
    api_key = None
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass

    if not api_key or str(api_key).strip().lower() in PLACEHOLDERS:
        raise ValueError(
            "Groq API key is missing or still set to the placeholder in .streamlit/secrets.toml. "
            "Please replace it with your real Groq API key."
        )

    return ChatGroq(
        model=MODEL_NAME,
        temperature=temperature,
        api_key=api_key
    )
