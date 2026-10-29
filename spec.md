# SPEC.md

Paste a meeting transcript, get a summary and action items. A critic flags gaps, a human approves tasks, then draft emails and a timeline are produced.

## Graph
- START → extract_summary and extract_actions (parallel) → critic
- critic → revise if issues and loops < MAX_CRITIC_LOOPS (2), else → human_review
- revise → critic
- human_review (interrupt) → finalize → END

## State (src/state.py)
transcript: str, summary: str, actions: list[ActionItem], issues: list[str], loops: int, trace: Annotated[list[str], operator.add], approved: list[ActionItem], drafts: list[EmailDraft], timeline: list[dict]

## Schemas (src/schemas.py)
- ActionItem: id: str, task: str, owner: str | None, due_date: str | None (YYYY-MM-DD), source_quote: str, notes: str = ""
- EmailDraft: recipient: str, subject: str, body: str, task_ids: list[str]
- Output wrappers as needed: SummaryOutput, ActionList, CriticOutput(issues), ReviseOutput(summary, actions)

## Nodes (src/nodes.py)
Each appends its name to trace.
- extract_summary: transcript → summary. Must not touch actions.
- extract_actions: transcript → actions. Assign ids a1, a2... Owner None if not clearly stated. Never invent owners or dates.
- critic: transcript, summary, actions → issues (replaced each run). Flags missing owners, missing dates, unknown owners, contradictions. Must not edit actions or summary.
- revise: fix issues from transcript only, keep ids stable, loops += 1, clear issues. Unresolvable items stay None with a note.
- human_review: interrupt({summary, actions, issues}); resume value is the human's edited list. Sets approved. No side effects before interrupt.
- finalize: group approved by owner, one LLM-written draft per owner (task_ids set in code), build timeline sorted by due date. Sends nothing.
- route_after_critic: pure function, returns "revise" or "review".

## Prompts (prompts/)
summarize.txt, extract_actions.txt, critic.txt, revise.txt, email_drafter.txt

## Files
```
app.py
requirements.txt
README.md
AGENTS.md
SPEC.md
.gitignore
src/__init__.py, config.py, llm.py, schemas.py, state.py, nodes.py, graph.py
prompts/ (5 files above)
data/samples/ (3 transcripts + gold json)
evals/run_evals.py
tests/__init__.py, fake_llm.py, test_schemas.py, test_nodes.py, test_routing.py, test_graph.py
```

config.py: MODEL_NAME, MAX_CRITIC_LOOPS = 2, MAX_TRANSCRIPT_CHARS = 30000.
llm.py: get_llm() reads st.secrets["GROQ_API_KEY"] or env var.

## Milestones
- M0: scaffold tree, requirements pinned, pytest collects. Commit.
- M1: schemas, state, config, llm. Tests: valid/invalid due_date, state keys.
- M2: nodes + routing with fake LLM. Tests per node and all router branches.
- M3: graph without interrupt. Test: fan-out, loop cap, trace order, timeline sorted.
- M4: real interrupt/resume. Test: pause at review, resume with edits, approved reflects them.
- M5: app.py runs locally end to end.
- M6: 3 samples + run_evals.py prints precision/recall.
- M7: deploy to Streamlit Community Cloud, secret set, full run works.
- M8: README with diagram, GIF, live link, eval numbers.

Done when: M0–M5 pass, pytest passes with no API key, deployed app works, no emails sent.