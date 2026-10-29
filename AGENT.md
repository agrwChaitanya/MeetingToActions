# AGENTS.md

Read SPEC.md first. Build one milestone at a time.

## Stack
Python 3.11+, LangGraph, Streamlit, Groq (free tier, via langchain-groq), Pydantic v2, pytest.

## Rules
- Type hints everywhere. All LLM output parsed into Pydantic models.
- Prompts only in `prompts/*.txt`, never inline.
- Only `src/llm.py` imports Groq. Nodes receive the LLM as a parameter.
- Model name and loop cap only in `src/config.py`.
- Nodes return partial state updates; never mutate input state.
- Use `logging`, not `print`.
- No real email sending. No user data written to disk.
- Never commit secrets (`.streamlit/secrets.toml` stays gitignored).
- Build only what SPEC.md lists. Ask before adding files, features, or changing the graph.
- Before editing `graph.py`, `state.py`, or `nodes.py`, state a short plan and wait.
- Tests never call the real API. Use `tests/fake_llm.py`.
- Run `pytest -q` yourself and report results. Do not delete tests to pass.

## Commands
```
pip install -r requirements.txt
pytest -q
streamlit run app.py
```