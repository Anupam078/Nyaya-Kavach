"""
fine_tune_indicbert.py - Roadmap Task 1.3

WHAT THIS SCRIPT DOES, STEP BY STEP (read this before running):

1. Loads combined_training_data.json - every LabeledClause example you've
   accumulated so far, from every source (hand-labeled, synthetic, Ollama,
   Gemini).

2. Converts the 13 category names into integer IDs (0-12). Neural networks
   output numbers, not text - LABEL2ID/ID2LABEL below is the translation
   table in both directions.

3. Splits your data into a TRAINING set and a VALIDATION set. This is the
   most important concept to understand: the model only ever learns from
   the training set. The validation set is held back and never trained on,
   so that when we check accuracy on it, we're honestly testing whether the
   model generalized - not just memorized the exact examples it saw.

4. Tokenizes the clause text - converts words into the numeric IDs
   IndicBERT's vocabulary understands. This is mechanical, the tokenizer
   handles it.

5. Loads the PRETRAINED IndicBERT model and attaches a fresh classification
   head on top - a small new layer with 13 outputs (one score per category).
   IndicBERT already understands Hindi/English generally, from its original
   pretraining. Only this small new head starts untrained; fine-tuning
   adjusts both the head AND slightly nudges IndicBERT's existing weights
   to specialize for your task.

6. Trains for several epochs (full passes over the training data). Each
   epoch, the model's predictions are compared to the real labels, the
   error is measured, and the weights are adjusted slightly to reduce it.

7. Evaluates on the held-out validation set after training.

8. Saves the fine-tuned model to disk - a folder, not one file. This folder
   is what a FastAPI wrapper (Stage 1.3's "lightweight FastAPI/Flask
   wrapper") will load later to actually serve predictions.

HONEST EXPECTATION: with a few hundred examples spread across 13 categories,
accuracy will be mediocre this run - some categories may have too few
examples to learn well, or even to validate at all (see the WARNING this
script prints about categories with under 4 examples). That is expected,
not a bug. The goal of THIS run is proving the pipeline mechanics work
end-to-end. Re-run this exact script, unchanged, on your growing
combined_training_data.json as more data accumulates - accuracy should
improve as data grows.

SETUP (run once):
    pip install transformers datasets torch scikit-learn sentencepiece "accelerate>=1.1.0"
    (sentencepiece is required - IndicBERT's tokenizer needs it, and it's
    an easy-to-miss dependency that causes a confusing error without it.
    accelerate is required by the Trainer class itself for PyTorch device
    management - also easy to miss, transformers doesn't always pull it in
    automatically depending on your install method.)

RUN:
    python fine_tune_indicbert.py
"""

import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

MODEL_NAME = "google/muril-base-cased"  # switched from ai4bharat/indic-bert, which
# AI4Bharat recently gated (requires HF login + approval, unpredictable timeline).
# MURIL is Google's equivalent for Indian languages (17 languages incl. Hindi),
# same general architecture family, hosted under Google's org - not expected to
# be gated. If you specifically want to return to true IndicBERT later, request
# access at https://huggingface.co/ai4bharat/indic-bert while logged into a free
# HF account, then run `huggingface-cli login` locally once approved.
DATA_PATH = Path(__file__).parent.parent / "synthetic-data" / "combined_training_data.json"
OUTPUT_DIR = Path(__file__).parent / "indicbert-clause-classifier"

CATEGORIES = [
    "interest_finance_terms", "principal_repayment_schedule", "penalty_default_consequences",
    "duration_term", "termination_notice_period", "wage_payment_terms", "working_hours_conditions",
    "ownership_transfer", "security_collateral_pledge", "mandatory_disclosure_documentation",
    "dispute_resolution", "renewal_auto_renewal", "other_uncategorized",
]
LABEL2ID = {c: i for i, c in enumerate(CATEGORIES)}
ID2LABEL = {i: c for c, i in LABEL2ID.items()}


def load_data() -> tuple[list[str], list[int]]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    texts = [item["text"] for item in raw]
    labels = [LABEL2ID[item["clause_category"]] for item in raw]
    return texts, labels


def split_data(texts: list[str], labels: list[int]):
    counts = Counter(labels)
    too_small = [ID2LABEL[l] for l, c in counts.items() if c < 4]
    if too_small:
        print(f"WARNING: these categories have fewer than 4 examples - a meaningful "
              f"train/validation split isn't really possible for them yet: {too_small}")
        print("This is expected with a small dataset. It will resolve as you add more data.\n")

    try:
        return train_test_split(texts, labels, test_size=0.15, random_state=42, stratify=labels)
    except ValueError:
        print("Stratified split failed (some category too small to stratify) - using a plain random split instead.\n")
        return train_test_split(texts, labels, test_size=0.15, random_state=42)


def main():
    # Deliberately deferred imports: these are heavy (torch especially) and
    # we want the fast, dependency-light data checks above to run and print
    # their warnings even if the ML libraries aren't installed yet.
    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments,
    )

    texts, labels = load_data()
    print(f"Loaded {len(texts)} examples across {len(set(labels))} of {len(CATEGORIES)} categories.\n")

    train_texts, val_texts, train_labels, val_labels = split_data(texts, labels)
    print(f"Train: {len(train_texts)}  Validation: {len(val_texts)}\n")

    print(f"Downloading/loading tokenizer and model: {MODEL_NAME} (one-time download, cached after)...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=128)

    train_ds = Dataset.from_dict({"text": train_texts, "label": train_labels}).map(tokenize, batched=True)
    val_ds = Dataset.from_dict({"text": val_texts, "label": val_labels}).map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(CATEGORIES), id2label=ID2LABEL, label2id=LABEL2ID
    )

    def compute_metrics(eval_pred):
        logits, eval_labels = eval_pred
        preds = np.argmax(logits, axis=1)
        return {
            "accuracy": accuracy_score(eval_labels, preds),
            "f1_macro": f1_score(eval_labels, preds, average="macro", zero_division=0),
        }

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        num_train_epochs=8,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        eval_strategy="epoch",
        save_strategy="no",
        logging_steps=5,
        learning_rate=2e-5,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    print("Starting training...\n")
    trainer.train()
    metrics = trainer.evaluate()
    print(f"\nFinal validation metrics: {metrics}")
    print("\nRemember: f1_macro treats every category equally regardless of size - a low")
    print("score here with this little data is expected, not alarming. Watch this number")
    print("trend upward across future re-runs as your dataset grows, that's the real signal.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"\nModel saved to {OUTPUT_DIR}")

    # Append this run's results to a running log, so future re-runs (as your
    # dataset grows) are easy to compare against past ones instead of relying
    # on memory or scrolled-away terminal output.
    log_path = Path(__file__).parent / "training_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    log.append({
        "timestamp": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "num_examples": len(texts),
        "num_train": len(train_texts),
        "num_val": len(val_texts),
        "eval_accuracy": metrics.get("eval_accuracy"),
        "eval_f1_macro": metrics.get("eval_f1_macro"),
        "eval_loss": metrics.get("eval_loss"),
    })
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Run logged to {log_path} - {len(log)} run(s) recorded so far.")


if __name__ == "__main__":
    main()
