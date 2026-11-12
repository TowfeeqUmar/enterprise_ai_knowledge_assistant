"""
Small, zero-cost retrieval evaluation utility.
Run from the project root: python evaluation/evaluate.py

Edit TEST_CASES to match your uploaded sample documents.
It reports Hit@K: whether an expected source document appears in top-K retrieval.
For answer quality / faithfulness, optionally connect RAGAS to a prepared dataset;
this script deliberately avoids requiring a paid evaluator.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.rag_pipeline import retrieve


TEST_CASES = [
    {
        "question": "How many annual leave days are provided?",
        "expected_filename": "hr_policy.txt"
    },
    {
        "question": "How many sick leave days are provided?",
        "expected_filename": "hr_policy.txt"
    },
    {
        "question": "How long is maternity leave?",
        "expected_filename": "hr_policy.txt"
    },
    {
        "question": "When is salary credited?",
        "expected_filename": "hr_policy.txt"
    },
    {
        "question": "How many days can employees work remotely?",
        "expected_filename": "it_policy.txt"
    },
    {
        "question": "Is manager approval required for remote work?",
        "expected_filename": "it_policy.txt"
    },
    {
        "question": "How should company laptops be protected?",
        "expected_filename": "it_policy.txt"
    },
    {
        "question": "What should employees do after a security incident?",
        "expected_filename": "it_policy.txt"
    }
]


def main():
    if not TEST_CASES:
        print("Add question + expected_filename entries to TEST_CASES before running evaluation.")
        return
    hits = 0
    reciprocal_ranks = []
    for case in TEST_CASES:
        results = retrieve(case["question"], top_k=5, min_similarity=0.0)
        rank = next((i for i, result in enumerate(results, 1)
                     if result["metadata"].get("filename") == case["expected_filename"]), None)
        hit = rank is not None
        hits += int(hit)
        reciprocal_ranks.append(1 / rank if rank else 0)
        print(f"{'HIT' if hit else 'MISS'} | {case['question']} | rank={rank}")
    total = len(TEST_CASES)
    print(f"\nHit@5: {hits / total:.2%}")
    print(f"MRR: {sum(reciprocal_ranks) / total:.3f}")

if __name__ == "__main__":
    main()
