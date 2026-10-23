"""Export retrieved chunk text independently of the vector database."""
from .core import InvalidSnapshot, digest, validate


def anchor(documents, document, text):
    """Find a unique exact source substring; reject ambiguous provenance."""
    if document not in documents or not isinstance(text, str) or not text:
        raise InvalidSnapshot("anchor needs a known document and nonempty text")
    source = documents[document]
    start = source.find(text)
    if start < 0:
        raise InvalidSnapshot(f"chunk is not an exact source substring: {document}")
    if source.find(text, start + 1) >= 0:
        raise InvalidSnapshot(f"ambiguous repeated text in {document}; supply explicit offsets")
    return {"document": document, "start": start, "end": start + len(text), "text": text}


def from_chunks(documents, cases):
    """Convert {document, text} chunks to a snapshot. Retrieval order is rank order.

    Normalized/enriched chunks require explicit canonical source offsets instead.
    """
    snapshot = {"version": 1,
                "documents": {key: {"text": text, "sha256": digest(text)}
                              for key, text in documents.items()}, "cases": []}
    for case in cases:
        snapshot["cases"].append({"id": case["id"], "question": case["question"],
                                 **{field: [anchor(documents, item["document"], item["text"])
                                            for item in case[field]]
                                    for field in ("evidence", "retrieved")}})
    return validate(snapshot)
