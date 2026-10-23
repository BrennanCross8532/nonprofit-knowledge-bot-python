from src.knowledge_bot import KnowledgeRequest, answer_request


def test_receipt_question_routes_to_receipt_notes_and_returns_answer() -> None:
    request = KnowledgeRequest("How do we issue a donor receipt?", "finance")
    result = answer_request(
        request,
        lambda question: [{"metadata": {"text": "Send the receipt after the gift is recorded."}}],
        lambda question, notes: notes[0],
    )
    assert result == {
        "topic": "donor_receipt",
        "answer": "Send the receipt after the gift is recorded.",
        "sources": ["Send the receipt after the gift is recorded."],
    }
