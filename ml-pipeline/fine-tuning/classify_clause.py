"""
classify_clause.py - completes Stage 1.3 (inference wrapper for the
fine-tuned classifier), and is the building block Stage 3's risk engine
will call to classify each segmented clause.

USAGE (interactive testing):
    python classify_clause.py

USAGE (as a module, from other scripts):
    from classify_clause import ClauseClassifier
    clf = ClauseClassifier()
    category, confidence = clf.classify("Wage: Rs. 470 per day, paid weekly.")
"""

from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_DIR = Path(__file__).parent / "indicbert-clause-classifier"


class ClauseClassifier:
    """Loads the fine-tuned model once; classify() is then fast to call repeatedly."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        if not model_dir.exists():
            raise FileNotFoundError(
                f"No trained model found at {model_dir}. Run fine_tune_indicbert.py first."
            )
        print(f"Loading model from {model_dir}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.eval()  # inference mode - disables dropout etc., not needed for training here
        print("Model loaded.\n")

    def classify(self, text: str) -> tuple[str, float]:
        """
        Returns (predicted_category, confidence) where confidence is the
        model's own probability estimate (0-1) for its top prediction.

        NOTE: confidence is the model's self-reported certainty, not a
        guarantee of correctness - a model can be confidently wrong,
        especially on categories it saw few training examples for. Don't
        treat a high confidence score as proof of accuracy on its own.
        """
        inputs = self.tokenizer(text, truncation=True, padding=True, max_length=128, return_tensors="pt")
        with torch.no_grad():  # no gradient tracking needed for inference - faster, less memory
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=1)[0]

        predicted_id = int(torch.argmax(probabilities))
        predicted_category = self.model.config.id2label[predicted_id]
        confidence = float(probabilities[predicted_id])
        return predicted_category, confidence

    def classify_with_all_scores(self, text: str) -> dict[str, float]:
        """Returns every category's probability, not just the top one - useful for
        debugging borderline predictions or building a 'top-3 guesses' UI later."""
        inputs = self.tokenizer(text, truncation=True, padding=True, max_length=128, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=1)[0]
        return {
            self.model.config.id2label[i]: float(probabilities[i])
            for i in range(len(probabilities))
        }


if __name__ == "__main__":
    clf = ClauseClassifier()

    print("Interactive clause classifier - type a clause (Hindi or English), or 'quit' to exit.\n")
    while True:
        text = input("Clause text> ").strip()
        if text.lower() in ("quit", "exit", "q"):
            break
        if not text:
            continue

        category, confidence = clf.classify(text)
        print(f"  -> {category}  (confidence: {confidence:.1%})")

        all_scores = clf.classify_with_all_scores(text)
        top3 = sorted(all_scores.items(), key=lambda x: -x[1])[:3]
        print(f"  Top 3: {', '.join(f'{cat} ({score:.1%})' for cat, score in top3)}\n")
