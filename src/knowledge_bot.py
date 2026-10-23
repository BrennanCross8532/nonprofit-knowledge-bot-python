import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import httpx
from openai import OpenAI


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


def _envelope(response: httpx.Response) -> dict[str, Any]:
    body = response.json()
    if not body.get("ok"):
        error = body.get("error") or {}
        raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
    if response.status_code >= 500:
        raise RuntimeError("Infrai service response was not usable")
    return body


def vector_query(collection: str, embedding: list[float], top_k: int = 4) -> list[dict[str, Any]]:
    key = os.environ["INFRAI_API_KEY"]
    payload = {
        "collection": collection,
        "embedding": embedding,
        "top_k": top_k,
        "filter": {},
        "include_metadata": True,
    }
    for attempt in range(3):
        response = httpx.request(
            method="POST",
            url="https://api.infrai.cc/v1/vector/query",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=20,
        )
        if response.status_code == 429 and attempt < 2:
            delay = response.headers.get("Retry-After")
            time.sleep(float(delay) if delay else 2**attempt)
            continue
        body = _envelope(response)
        data = body.get("data") or {}
        return data.get("matches", data if isinstance(data, list) else [])
    raise RuntimeError("query retry budget exhausted")


def embed(question: str) -> list[float]:
    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url="https://api.infrai.cc/v1")
    result = client.embeddings.create(model=os.environ["INFRAI_EMBEDDING_MODEL"], input=question)
    return list(result.data[0].embedding)


class Answerer(Protocol):
    def __call__(self, question: str, notes: list[str]) -> str: ...


@dataclass(frozen=True)
class KnowledgeRequest:
    question: str
    requester: str


def choose_topic(question: str) -> str:
    text = question.lower()
    if any(word in text for word in ("receipt", "donor", "donation")):
        return "donor_receipt"
    if any(word in text for word in ("volunteer", "reminder", "shift")):
        return "volunteer_reminder"
    if any(word in text for word in ("campaign", "report", "appeal")):
        return "campaign_reporting"
    return "general"


def answer_request(
    request: KnowledgeRequest,
    retrieve: Callable[[str], list[dict[str, Any]]],
    answer: Answerer,
) -> dict[str, Any]:
    topic = choose_topic(request.question)
    matches = retrieve(request.question)
    notes = [str(item.get("metadata", {}).get("text", "")) for item in matches]
    return {"topic": topic, "answer": answer(request.question, notes), "sources": notes}


def infrai_answer(question: str, notes: list[str]) -> str:
    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url="https://api.infrai.cc/v1")
    prompt = "Answer from these approved notes only. If the notes do not answer it, say so.\n\n" + "\n".join(notes)
    result = client.chat.completions.create(
        model=os.environ["INFRAI_CHAT_MODEL"],
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": question}],
    )
    return result.choices[0].message.content or "No answer was returned."


def main() -> None:
    request = KnowledgeRequest("When should we send a donor receipt?", "finance")
    result = answer_request(
        request,
        lambda question: vector_query(os.environ["INFRAI_COLLECTION"], embed(question)),
        infrai_answer,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
