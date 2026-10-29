
from pathlib import Path
import csv

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent
CHUNKS_FILE = ROOT / "outputs" / "policy_chunks.csv"


class PolicyRetriever:
    def __init__(self, chunks_file=CHUNKS_FILE):
        self.chunks = []

        with open(chunks_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.chunks.append({
                    "source": row["source_file"],
                    "text": row["chunk_text"],
                })

        if not self.chunks:
            raise ValueError("No policy chunks found.")

        # Fit TF-IDF on all policy chunk texts.
        self.vectorizer = TfidfVectorizer()
        self.chunk_vectors = self.vectorizer.fit_transform(
            [chunk["text"] for chunk in self.chunks]
        )

    def retrieve(self, query, k=3):
        """Return the top-k policy chunks ranked by cosine similarity."""
        if not query or not query.strip():
            return []

        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(
            query_vector, self.chunk_vectors
        ).flatten()

        # Sort by descending similarity; retain original order for ties.
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: (-scores[i], i)
        )[:max(0, k)]

        return [
            {
                "source": self.chunks[i]["source"],
                "score": float(scores[i]),
                "text": self.chunks[i]["text"],
            }
            for i in ranked_indices
        ]


if __name__ == "__main__":
    retriever = PolicyRetriever()

    query = "refund policy late delivery"
    results = retriever.retrieve(query, k=3)

    print(f"Query: {query}")
    print("\nTop retrieved chunks:")

    for rank, result in enumerate(results, start=1):
        print(f"\nRank: {rank}")
        print(f"Source: {result['source']}")
        print(f"Score: {result['score']:.4f}")
        print(f"Text: {result['text']}")

    # Check the assignment's reference result.
    assert len(results) == 3, "Expected three retrieved chunks."
    assert all(
        result["source"] == "refund_policy.txt"
        for result in results
    ), "Reference check failed: top three should be refund policy chunks."

    print("\nReference check passed: all top three chunks are from refund_policy.txt.")
