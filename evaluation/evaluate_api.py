
import json
import re
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8000/ask"

# Positive tests: expected answer and supporting document.
ANSWER_TESTS = [
    {
        "question": "How many sick leave days are employees entitled to?",
        "expected_answer": "12 days",
        "expected_filename": "hr_policy.txt",
    },
    {
        "question": "How many annual leave days do employees receive?",
        "expected_answer": "18 days",
        "expected_filename": "hr_policy.txt",
    },
    {
        "question": "How long is maternity leave?",
        "expected_answer": "26 weeks",
        "expected_filename": "hr_policy.txt",
    },
    {
        "question": "When is salary credited?",
        "expected_answer": "last working day",
        "expected_filename": "hr_policy.txt",
    },
    {
        "question": "How many days per week can employees work remotely?",
        "expected_answer": "2 days",
        "expected_filename": "it_policy.txt",
    },
    {
        "question": "Is manager approval required for remote work?",
        "expected_answer": "approval",
        "expected_filename": "it_policy.txt",
    },
    {
        "question": "How should company laptops be protected?",
        "expected_answer": "password",
        "expected_filename": "it_policy.txt",
    },
    {
        "question": "What should employees do after a security incident?",
        "expected_answer": "immediately",
        "expected_filename": "it_policy.txt",
    },
]

# Negative tests: information not present in the uploaded documents.
ABSTENTION_TESTS = [
    "How much pension contribution does the company provide?",
    "What is the company's office address?",
]


def ask_api(question):
    payload = json.dumps({"question": question}).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def check_citation(response, expected_filename):
    """Check whether a cited source number maps to the expected file."""
    answer = response.get("answer", "")
    sources = response.get("sources", [])

    cited_numbers = {
        int(number)
        for number in re.findall(
            r"\[Source\s+(\d+)\]",
            answer,
            flags=re.IGNORECASE,
        )
    }

    for number in cited_numbers:
        if 1 <= number <= len(sources):
            source = sources[number - 1]
            if source.get("filename") == expected_filename:
                return True

    return False


def percentage(passed, total):
    if total == 0:
        return 0.0
    return passed / total * 100


def main():
    answer_passed = 0
    citation_passed = 0
    abstention_passed = 0
    api_errors = 0

    print("\n========== RAG ANSWER EVALUATION ==========\n")

    # Test factual answers and citations.
    for index, test in enumerate(ANSWER_TESTS, start=1):
        question = test["question"]

        try:
            result = ask_api(question)

            answer = result.get("answer", "")
            found = result.get("found", False)

            answer_ok = (
                found is True
                and test["expected_answer"].casefold()
                in answer.casefold()
            )

            citation_ok = (
                found is True
                and check_citation(result, test["expected_filename"])
            )

            answer_passed += int(answer_ok)
            citation_passed += int(citation_ok)

            print(f"TEST {index}: {question}")
            print(f"ANSWER: {answer}")
            print(f"ANSWER ACCURACY: {'PASS' if answer_ok else 'FAIL'}")
            print(f"CITATION ACCURACY: {'PASS' if citation_ok else 'FAIL'}")
            print(f"SOURCES: {len(result.get('sources', []))}")
            print("-" * 60)

        except Exception as exc:
            api_errors += 1
            print(f"TEST {index}: ERROR - {question}")
            print(f"DETAILS: {exc}")
            print("-" * 60)

    # Test unsupported questions and abstention.
    print("\n========== ABSTENTION EVALUATION ==========\n")

    for index, question in enumerate(ABSTENTION_TESTS, start=1):
        try:
            result = ask_api(question)

            answer = result.get("answer", "")
            sources = result.get("sources", [])

            abstained = (
                result.get("found") is False
                and len(sources) == 0
                and "couldn't find this information"
                in answer.casefold()
            )

            abstention_passed += int(abstained)

            print(f"TEST {index}: {question}")
            print(f"ANSWER: {answer}")
            print(f"FOUND: {result.get('found')}")
            print(f"SOURCES: {len(sources)}")
            print(f"ABSTENTION: {'PASS' if abstained else 'FAIL'}")
            print("-" * 60)

        except Exception as exc:
            api_errors += 1
            print(f"TEST {index}: ERROR - {question}")
            print(f"DETAILS: {exc}")
            print("-" * 60)

    # Final report.
    total_positive = len(ANSWER_TESTS)
    total_negative = len(ABSTENTION_TESTS)

    print("\n========== FINAL EVALUATION REPORT ==========\n")

    print(
        f"Answer accuracy: "
        f"{answer_passed}/{total_positive} "
        f"({percentage(answer_passed, total_positive):.2f}%)"
    )

    print(
        f"Citation accuracy: "
        f"{citation_passed}/{total_positive} "
        f"({percentage(citation_passed, total_positive):.2f}%)"
    )

    print(
        f"Abstention accuracy: "
        f"{abstention_passed}/{total_negative} "
        f"({percentage(abstention_passed, total_negative):.2f}%)"
    )

    total_passed = (
        answer_passed + citation_passed + abstention_passed
    )
    total_checks = total_positive * 2 + total_negative

    print(
        f"\nTotal checks passed: "
        f"{total_passed}/{total_checks} "
        f"({percentage(total_passed, total_checks):.2f}%)"
    )

    print(f"API errors: {api_errors}")

    if api_errors:
        print("\nSome tests could not complete. Check the API and rerun.")
    elif total_passed == total_checks:
        print("\nALL EVALUATION CHECKS PASSED.")
    else:
        print("\nSome evaluation checks failed. Review the results above.")


if __name__ == "__main__":
    main()
