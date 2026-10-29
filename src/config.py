import os

MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite")
MAX_CRITIC_LOOPS: int = 2
MAX_TRANSCRIPT_CHARS: int = 12000
