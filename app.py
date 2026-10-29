import streamlit as st
import uuid
import pandas as pd
from langgraph.types import Command
from src.graph import graph
from src.schemas import ActionItem
from src.config import MAX_TRANSCRIPT_CHARS

st.set_page_config(
    page_title="Meeting Transcripts to Actions",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Meeting Transcripts to Actions")
st.markdown("Transform meeting transcripts into structured action items, review them, generate email drafts, and view a timeline.")

# Initialize session state variables
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "running" not in st.session_state:
    st.session_state.running = False

# Sidebar for controls and configuration
with st.sidebar:
    st.header("Controls")
    if st.button("Reset Session"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.transcript = ""
        st.session_state.running = False
        st.rerun()
    
    st.markdown("---")
    st.markdown("**About**")
    st.markdown("This app runs an end-to-end LangGraph workflow to extract, critique, revise, and finalize meeting action items.")

# Main input area
transcript_input = st.text_area(
    "Paste Meeting Transcript Here:",
    value=st.session_state.transcript,
    height=250,
    placeholder="Alice: We need to finish the Q3 report by Friday. Bob: I can help with the financials..."
)

col1, col2 = st.columns([1, 5])
with col1:
    run_button = st.button("Run Processor", type="primary")

config = {"configurable": {"thread_id": st.session_state.thread_id}}

if run_button and transcript_input.strip():
    if len(transcript_input) > MAX_TRANSCRIPT_CHARS:
        st.error(f"Transcript exceeds maximum length of {MAX_TRANSCRIPT_CHARS} characters (current length: {len(transcript_input)}).")
    else:
        st.session_state.transcript = transcript_input
        initial_state = {
            "transcript": transcript_input,
            "summary": "",
            "actions": [],
            "issues": [],
            "loops": 0,
            "trace": [],
            "approved": [],
            "drafts": [],
            "timeline": []
        }
        with st.spinner("Processing meeting transcript... (Extracting summary & actions, running critic & revision)"):
            try:
                graph.invoke(initial_state, config)
            except Exception as e:
                st.error(f"Error during graph execution: {e}")

# Check current graph state
try:
    snapshot = graph.get_state(config)
except Exception:
    snapshot = None

if snapshot:
    next_nodes = snapshot.next
    values = snapshot.values

    # Check if paused at human_review
    if "human_review" in next_nodes or (snapshot.tasks and any(t.interrupts for t in snapshot.tasks)):
        st.info("⏸️ Graph paused at **Human Review**. Please review the summary, critique issues, and action items below, make any edits, and click **Approve & Continue**.")
        
        # Display summary
        st.subheader("📝 Meeting Summary")
        st.write(values.get("summary", "No summary available."))
        
        # Display issues flagged by critic
        issues = values.get("issues", [])
        if issues:
            st.warning("⚠️ Critic Issues Flagged:")
            for issue in issues:
                st.markdown(f"- {issue}")
        else:
            st.success("✨ Critic found no issues.")

        # Display and edit action items
        st.subheader("🛠️ Review & Edit Action Items")
        actions_list = values.get("actions", [])
        
        actions_data = [
            {
                "id": item.id if hasattr(item, "id") else item.get("id", ""),
                "task": item.task if hasattr(item, "task") else item.get("task", ""),
                "owner": item.owner if hasattr(item, "owner") else item.get("owner", None),
                "due_date": item.due_date if hasattr(item, "due_date") else item.get("due_date", None),
                "source_quote": item.source_quote if hasattr(item, "source_quote") else item.get("source_quote", ""),
                "notes": item.notes if hasattr(item, "notes") else item.get("notes", "")
            }
            for item in actions_list
        ]
        
        df = pd.DataFrame(actions_data)
        if df.empty:
            df = pd.DataFrame(columns=["id", "task", "owner", "due_date", "source_quote", "notes"])
            
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key="action_items_editor"
        )
        
        if st.button("Approve & Continue", type="primary"):
            updated_actions = []
            for _, row in edited_df.iterrows():
                updated_actions.append(
                    ActionItem(
                        id=str(row.get("id", f"a{_+1}")),
                        task=str(row.get("task", "")),
                        owner=str(row.get("owner")) if row.get("owner") and str(row.get("owner")) != "None" else None,
                        due_date=str(row.get("due_date")) if row.get("due_date") and str(row.get("due_date")) != "None" else None,
                        source_quote=str(row.get("source_quote", "")),
                        notes=str(row.get("notes", ""))
                    )
                )
            
            with st.spinner("Resuming graph execution (Finalizing drafts & timeline)..."):
                try:
                    graph.invoke(Command(resume=updated_actions), config)
                    st.success("Workflow completed successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error resuming graph: {e}")

    # Check if workflow is completed (no next nodes and draft/timeline present)
    elif not next_nodes and values.get("timeline"):
        st.success("🎉 Workflow Completed Successfully!")
        
        # Display Summary
        st.subheader("📝 Meeting Summary")
        st.write(values.get("summary", ""))
        
        # Display Email Drafts
        st.subheader("📧 Email Drafts")
        drafts = values.get("drafts", [])
        if drafts:
            for idx, draft in enumerate(drafts):
                recipient = draft.recipient if hasattr(draft, "recipient") else draft.get("recipient", "Unknown")
                subject = draft.subject if hasattr(draft, "subject") else draft.get("subject", "")
                body = draft.body if hasattr(draft, "subject") else draft.get("body", "")
                task_ids = draft.task_ids if hasattr(draft, "task_ids") else draft.get("task_ids", [])
                
                with st.expander(f"Draft to: {recipient} (Tasks: {', '.join(task_ids)})"):
                    st.markdown(f"**Subject:** {subject}")
                    st.text_area("Body", value=body, height=150, key=f"draft_body_{recipient}_{idx}")
                    
                    sent_key = f"email_sent_{recipient}_{idx}"
                    if sent_key not in st.session_state:
                        st.session_state[sent_key] = False
                        
                    col_send, col_status = st.columns([1, 3])
                    with col_send:
                        if st.button(f"📤 Send Email", key=f"send_btn_{recipient}_{idx}", disabled=st.session_state[sent_key]):
                            st.session_state[sent_key] = True
                            st.rerun()
                    with col_status:
                        if st.session_state[sent_key]:
                            st.success(f"✓ Simulated email successfully sent to {recipient}!")
        else:
            st.info("No email drafts generated.")
            
        # Display Timeline
        st.subheader("📅 Action Timeline (Sorted by Due Date)")
        timeline = values.get("timeline", [])
        if timeline:
            timeline_df = pd.DataFrame(timeline)
            st.dataframe(timeline_df, use_container_width=True)
            
            csv_data = timeline_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Timeline (CSV)",
                data=csv_data,
                file_name="action_timeline.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No timeline items.")
            
        # Display Trace
        with st.expander("🔍 Execution Trace"):
            st.write(values.get("trace", []))
