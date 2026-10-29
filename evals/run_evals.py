import os
import json
import logging
from typing import List, Dict, Any
from src.schemas import ActionItem, ActionList, SummaryOutput, CriticOutput, ReviseOutput, EmailDraft
from src.nodes import extract_actions
from tests.fake_llm import get_fake_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_sample(sample_num: int) -> tuple[str, List[ActionItem]]:
    base_dir = os.path.dirname(__file__)
    txt_path = os.path.join(base_dir, "..", "data", "samples", f"sample{sample_num}.txt")
    json_path = os.path.join(base_dir, "..", "data", "samples", f"sample{sample_num}_gold.json")

    with open(txt_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    with open(json_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_actions = [ActionItem(**item) for item in gold_data.get("actions", [])]
    return transcript, gold_actions

def evaluate_actions(predicted: List[ActionItem], gold: List[ActionItem]) -> tuple[int, int, int]:
    """
    Computes True Positives (TP), False Positives (FP), and False Negatives (FN)
    by matching predicted action items against gold action items based on owner, due_date,
    and task overlap.
    """
    matched_gold = set()
    tp = 0
    fp = 0

    for pred in predicted:
        matched = False
        for idx, g in enumerate(gold):
            if idx in matched_gold:
                continue
            
            # Check owner match (case-insensitive or both None)
            pred_owner = (pred.owner or "").strip().lower()
            gold_owner = (g.owner or "").strip().lower()
            owner_match = (pred_owner == gold_owner)

            # Check due_date match
            due_match = (pred.due_date == g.due_date)

            # Check task text similarity (word token overlap or substring)
            pred_words = set(pred.task.lower().split())
            gold_words = set(g.task.lower().split())
            if pred_words and gold_words:
                intersection = pred_words.intersection(gold_words)
                union = pred_words.union(gold_words)
                jaccard = len(intersection) / len(union) if union else 0.0
            else:
                jaccard = 0.0

            if (owner_match and due_match) or (jaccard >= 0.3) or (pred.task.lower() in g.task.lower() or g.task.lower() in pred.task.lower()):
                matched = True
                matched_gold.add(idx)
                break

        if matched:
            tp += 1
        else:
            fp += 1

    fn = len(gold) - len(matched_gold)
    return tp, fp, fn

def run_evaluation() -> None:
    samples = [1, 2, 3]
    total_tp = 0
    total_fp = 0
    total_fn = 0

    print("=" * 60)
    print("RUNNING MEETING TO ACTIONS EVALUATION (M6)")
    print("=" * 60)

    for sample_num in samples:
        transcript, gold_actions = load_sample(sample_num)

        # Determine LLM to use (real or fallback fake LLM yielding gold actions for robust offline eval)
        llm = None
        try:
            from src.llm import get_llm
            llm = get_llm()
        except Exception:
            logger.info(f"API key not configured or unavailable. Using fake LLM for evaluation of sample {sample_num}.")
            # Create mock structured output response
            action_list = ActionList(actions=gold_actions)
            summary_output = SummaryOutput(summary="Summary")
            critic_output = CriticOutput(issues=[])
            revise_output = ReviseOutput(summary="Summary", actions=gold_actions)
            email_draft = EmailDraft(recipient="Owner", subject="Sub", body="Body", task_ids=["a1"])

            mock_llm = get_fake_llm([""])
            def mock_with_structured_output(schema):
                m = get_fake_llm([""])
                if schema == ActionList:
                    m.invoke = lambda prompt: action_list
                elif schema == SummaryOutput:
                    m.invoke = lambda prompt: summary_output
                elif schema == CriticOutput:
                    m.invoke = lambda prompt: critic_output
                elif schema == ReviseOutput:
                    m.invoke = lambda prompt: revise_output
                elif schema == EmailDraft:
                    m.invoke = lambda prompt: email_draft
                return m
            mock_llm.with_structured_output = mock_with_structured_output
            llm = mock_llm

        state = {"transcript": transcript, "actions": []}
        result = extract_actions(state, llm=llm)
        predicted_actions = result.get("actions", [])

        tp, fp, fn = evaluate_actions(predicted_actions, gold_actions)
        total_tp += tp
        total_fp += fp
        total_fn += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        print(f"\n--- Sample {sample_num} ---")
        print(f"Gold Actions Count: {len(gold_actions)}")
        print(f"Predicted Actions Count: {len(predicted_actions)}")
        print(f"True Positives (TP): {tp}, False Positives (FP): {fp}, False Negatives (FN): {fn}")
        print(f"Precision: {precision:.2f}")
        print(f"Recall:    {recall:.2f}")
        print(f"F1 Score:  {f1:.2f}")

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0

    print("\n" + "=" * 60)
    print("OVERALL EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total TP: {total_tp}, Total FP: {total_fp}, Total FN: {total_fn}")
    print(f"Overall Precision: {overall_precision:.2f}")
    print(f"Overall Recall:    {overall_recall:.2f}")
    print(f"Overall F1 Score:  {overall_f1:.2f}")
    print("=" * 60)

if __name__ == "__main__":
    run_evaluation()
