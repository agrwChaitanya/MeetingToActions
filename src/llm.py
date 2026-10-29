import os
import logging
from langchain_groq import ChatGroq
from src.config import MODEL_NAME

logger = logging.getLogger(__name__)

def get_llm(temperature: float = 0.0) -> ChatGroq:
    """Returns a ChatGroq LLM instance configured with GROQ_API_KEY from env or streamlit secrets."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            pass

    if not api_key:
        logger.warning("GROQ_API_KEY not found in environment or streamlit secrets.")

    return ChatGroq(
        model=MODEL_NAME,
        temperature=temperature,
        api_key=api_key or "fake-key"
    )
