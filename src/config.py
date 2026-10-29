import os

MODEL_NAME: str = os.getenv("MODEL_NAME", "llama3-70b-8192")
MAX_CRITIC_LOOPS: int = 2
MAX_TRANSCRIPT_CHARS: int = 12000
