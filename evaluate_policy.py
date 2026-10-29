
from pathlib import Path
import csv

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import mock_llm


ROOT = Path(__file__).resolve().parent
POLICY_DIR = ROOT / "data" / "policies"
EVAL_FILE = ROOT / "data" / "raw" / "policy_eval.csv"


def load_questions():
    with open(EVAL_FILE, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise ValueError(f"No evaluation questions found in {EVAL_FILE}")

    required = {"question", "expected_doc", "expected_fact"}
    missing = required - set(rows[0].keys())
    if missing:
        raise ValueError(
            f"Missing columns in policy_eval.csv: {sorted(missing)}. "
            f"Found: {list(rows[0].keys())}"
        )

    return rows


def build_chunks(overlap):
    """Build 40-word chunks with the requested overlap."""
    if not 0 <= overlap < 40:
        raise ValueError("Overlap must be between 0 and 39.")

    chunks = []
    step = 40 - overlap

    for path in sorted(POLICY_DIR.glob("*.txt")):
        words = path.read_text(encoding="utf-8").split()

        start = 0
        while start < len(words):
            chunk_words = words[start:start + 40]
            if not chunk_words:
                break

            chunks.append({
                "source": path.name,
                "text": " ".join(chunk_words),
            })

            # Stop after the first chunk reaching or passing the end.
            if start + 40 >= len(words):
                break

            start += step

    return chunks


def get_answer_text(response):
    """Extract text from the mock LLM response."""
    if isinstance(response, str):
        return response

    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return str(response)


def evaluate(overlap):
    chunks = build_chunks(overlap)

    vectorizer = TfidfVectorizer()
    chunk_vectors = vectorizer.fit_transform(
        [chunk["text"] for chunk in chunks]
    )

    def retrieve(query, k=3):
        query_vector = vectorizer.transform([query])
        scores = cosine_similarity(
            query_vector, chunk_vectors
        ).flatten()

        indices = sorted(
            range(len(scores)),
            key=lambda i: (-scores[i], i)
        )[:k]

        return [
            {
                **chunks[i],
                "score": float(scores[i]),
            }
            for i in indices
        ]

    rows = load_questions()
    results = []

    for row in rows:
        question = row["question"].strip()
        expected_doc = row["expected_doc"].strip()
        expected_fact = row["expected_fact"]

        retrieved = retrieve(question, k=3)
        sources = [item["source"] for item in retrieved]

        context = "\n".join(
            f'[{item["source"]}]\n{item["text"]}'
            for item in retrieved
        )

        system_message = {
            "role": "system",
            "content": (
                "POLICY ASSISTANT: Answer using only the supplied policy "
                "context. Do not use outside knowledge or invent facts. "
                "If the supplied context does not contain the answer, "
                "respond with a sentence beginning exactly "
                "'I could not find' and explain that the information "
                "was not found in the supplied policy context."
            ),
        }

        user_message = {
            "role": "user",
            "content": f"CONTEXT:\n{context}\nQUESTION:\n{question}",
        }

        response = mock_llm.chat([system_message, user_message])
        answer_text = get_answer_text(response).strip()

        # A non-empty expected_doc identifies an answerable question.
        #answerable = bool(expected_doc)
        answerable = (
           bool(expected_doc)
           and expected_doc.strip().upper() != "NONE"
        )
        
        doc_hit = (
            expected_doc in sources
            if answerable else None
        )
        fact_hit = (
            expected_fact in answer_text
            if answerable and expected_fact else (
                False if answerable else None
            )
        )
        fallback_hit = (
            answer_text.startswith("I could not find")
            if not answerable else None
        )

        results.append({
            "question": question,
            "expected_doc": expected_doc,
            "expected_fact": expected_fact,
            "answerable": answerable,
            "retrieved_sources": "; ".join(sources),
            "answer": answer_text,
            "doc_hit": doc_hit,
            "fact_hit": fact_hit,
            "fallback_hit": fallback_hit,
        })

    answerable_rows = [r for r in results if r["answerable"]]
    unanswerable_rows = [r for r in results if not r["answerable"]]

    summary = {
        "overlap": overlap,
        "chunk_count": len(chunks),
        "answerable_total": len(answerable_rows),
        "expected_doc_hits": sum(r["doc_hit"] for r in answerable_rows),
        "expected_fact_hits": sum(r["fact_hit"] for r in answerable_rows),
        "unanswerable_total": len(unanswerable_rows),
        "fallback_hits": sum(r["fallback_hit"] for r in unanswerable_rows),
    }

    return summary, results


def print_summary(summary):
    overlap = summary["overlap"]
    label = "Overlap 10" if overlap == 10 else "Zero overlap"

    print(f"\n=== {label} ===")
    print(f"Chunks created: {summary['chunk_count']}")
    print("\nMetric                              Result")
    print("----------------------------------  -------")
    print(
        "Answerable: expected_doc in top 3  "
        f"{summary['expected_doc_hits']}/{summary['answerable_total']}"
    )
    print(
        "Answerable: expected_fact present  "
        f"{summary['expected_fact_hits']}/{summary['answerable_total']}"
    )
    print(
        "Unanswerable: correct fallback     "
        f"{summary['fallback_hits']}/{summary['unanswerable_total']}"
    )


def main():
    # Run the same evaluation using both chunking strategies.
    for overlap in (10, 0):
        summary, results = evaluate(overlap)
        print_summary(summary)

        # Save detailed question-level results for inspection.
        output_file = ROOT / "outputs" / (
            "policy_eval_overlap10.csv"
            if overlap == 10
            else "policy_eval_overlap0.csv"
        )

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = [
                "question",
                "expected_doc",
                "expected_fact",
                "answerable",
                "retrieved_sources",
                "answer",
                "doc_hit",
                "fact_hit",
                "fallback_hit",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"Detailed results saved to: {output_file}")

        # Identify answerable questions that fail with zero overlap.
        if overlap == 0:
            failures = [
                r for r in results
                if r["answerable"]
                and (not r["doc_hit"] or not r["fact_hit"])
            ]

            print("\nAnswerable questions that failed with zero overlap:")
            if failures:
                for item in failures:
                    print(f"\nQuestion: {item['question']}")
                    print(f"Expected document: {item['expected_doc']}")
                    print(f"Retrieved sources: {item['retrieved_sources']}")
                    print(f"Expected fact: {item['expected_fact']!r}")
                    print(f"Generated answer: {item['answer']}")
            else:
                print("No failures found; compare with the assignment reference.")


if __name__ == "__main__":
    main()
