
from policy_retrieval import PolicyRetriever
import mock_llm


retriever = PolicyRetriever()


def answer(question):
    # Retrieve the three most relevant policy chunks.
    results = retriever.retrieve(question, k=3)

    # Build the context: each source filename appears on its own line.
    context_parts = []
    sources = []

    for result in results:
        source = result["source"]
        chunk_text = result["text"]

        context_parts.append(f"[{source}]\n{chunk_text}")

        if source not in sources:
            sources.append(source)

    context = "\n".join(context_parts)

    # System message instructs the model to use only the supplied context.
    system_message = {
        "role": "system",
        "content": (
            "POLICY ASSISTANT: Answer the user's question using only "
            "the supplied policy context. Do not use outside knowledge "
            "or make up policy details. If the context does not contain "
            "the answer, say that you could not find the information "
            "in the supplied policy context."
        ),
    }

    # Keep this message in the exact required format.
    user_message = {
        "role": "user",
        "content": (
            f"CONTEXT:\n{context}\nQUESTION:\n{question}"
        ),
    }

    # Send exactly two messages to the mock LLM.
    #response = mock_llm.chat([system_message, user_message])

    #return {
        #"answer": response,
        #"sources": sources,
    #}
    
    #Send exactly two messages to the mock LLM.
    response = mock_llm.chat([system_message, user_message])

    # Extract the generated answer text.
    answer_text = response.choices[0].message.content

    return {
       "answer": answer_text,
       "sources": sources,
    }

if __name__ == "__main__":
    question = "What refund applies to a delivery delayed by more than 45 minutes?"
    result = answer(question)

    print("Question:", question)
    print("\nAnswer:")
    print(result["answer"])
    print("\nSources used:")
    for source in result["sources"]:
        print("-", source)
