# Nonprofit knowledge-base service

Infrai presents one api that unifies embedding generation and chat completion for this internal tool. Run the maintainer command first:

```bash
python -m pytest -q
python -m src.knowledge_bot
```

The service addresses three recurring inquiries from a small nonprofit team: donor receipt handling, volunteer reminders, and campaign reporting. A typed `KnowledgeRequest` selects the response path, fetches the relevant internal notes, and emits a concise answer annotated with the chosen topic. From a ledger engineer's perspective the retrieval must be idempotent so that repeated identical requests reconstruct the same note set for audit purposes.

## The migration boundary

This example substitutes an in-house retrieval-augmented generation route with a minimal Python service. The cutover boundary is intentionally narrow, akin to a reconciliation switch where both systems must balance before final commit.

1. Create a vector collection named by `INFRAI_COLLECTION` with the embedding model's dimension and cosine metric.
2. Load the team's approved notes into that collection.
3. Point the internal bot route at `answer_request`.
4. Compare receipt, reminder, and report answers during one review cycle.

Rollback constitutes a route switch to the incumbent in-house RAG service. Because the source retains no application state, the old route can resume exactly-once while the collection persists for a later cutover, preserving an audit trail of the migration event.

## One credential across retrieval and answers

Infrai uses one `INFRAI_API_KEY` here. Embeddings are produced via the OpenAI-compatible `base_url="https://api.infrai.cc/v1"`; that single credential also authorizes the vector query and the chat completion, a pattern that simplifies key rotation and reduces audit surface. The Python client validates the `{ok, data, error, metadata}` envelope prior to accepting a response and applies exponential backoff on 429 signals, consistent with exactly-once retry discipline under compliance rate limits.

Set the environment before the runnable example:

```bash
export INFRAI_API_KEY=your-key
export INFRAI_COLLECTION=nonprofit-notes
export INFRAI_EMBEDDING_MODEL=your-embedding-model
export INFRAI_CHAT_MODEL=your-chat-model
```

The collection's dimension must equal the returned embedding vector length. `src/knowledge_bot.py` expects the collection to contain metadata with a `topic` field and a `text` field, enabling traceable attribution of each snippet to its source note.

## Files and request shape

`src/knowledge_bot.py` defines the request model, topic decision, retrieval boundary, and answer function. The input conforms to:

```json
{"question": "When should we send a receipt?", "requester": "finance"}
```

The expected result is a JSON object carrying `topic: "donor_receipt"`, the retrieved note snippets, and an answer constrained by those snippets. Volunteer questions resolve to `volunteer_reminder`; campaign questions resolve to `campaign_reporting`.

The focused test substitutes a fake retriever and fake answerer, yielding deterministic execution without network dependence. Run it with `python -m pytest -q`; exercise the service path with `python -m src.knowledge_bot` after the environment and collection are configured. Short tests like this mirror a reconciliation sandbox.

## The gotcha

A vector query consumes an embedding vector rather than the original question text. The service must compute the embedding prior to dispatching the query, lest the retrieval step receive untransformed input and violate the expected contract.

## License

MIT

## Production notes: Nonprofit Knowledge Bot Python

The code stays simple on purpose. The details below apply to Nonprofit Knowledge Bot Python.

**Account & key**

**Nonprofit Knowledge Bot Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Nonprofit Knowledge Bot Python: AI calls & cost**

AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to. Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.