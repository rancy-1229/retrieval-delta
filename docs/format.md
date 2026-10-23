# Snapshot v1

A snapshot is a UTF-8 JSON object:

```json
{
  "version": 1,
  "documents": {"policy": {"text": "Returns within 30 days."}},
  "cases": [{
    "id": "return-window",
    "question": "How long do I have?",
    "evidence": [{"document": "policy", "start": 15, "end": 22}],
    "retrieved": [{"document": "policy", "start": 0, "end": 22}]
  }]
}
```

`documents` and `cases` must be nonempty. Case IDs are unique. Evidence must be
nonempty; retrieval may be empty. Retrieved spans are in descending rank order.
Offsets count Unicode code points (Python string indexes), not UTF-8 bytes or
JavaScript UTF-16 code units. For JavaScript calculate offsets over `Array.from(text)`.
Each span uses a known document and integer bounds `0 <= start < end <= len(text)`.
An optional span `text` must exactly equal its source slice. An optional document
`sha256` is the lowercase SHA-256 hex digest of its UTF-8 text and must match.

No automatic Unicode/whitespace normalization is applied. Preserve the same
canonical source version for labeling and indexing. Equal text in a different
document is not equivalent provenance. Overlap is unioned independently per document.

Comparison requires the same document IDs/text, case IDs/questions and unioned
gold spans. Input case order and retrieval chunk IDs are irrelevant; rank order
is meaningful. Extra metadata is ignored. New/removed documents or cases require
an intentional baseline update even when unrelated to the evaluated questions.

JSON output contains baseline/candidate evaluations and changes ordered by
coverage delta. `passed` means only that the per-case coverage gate passed;
context expansion and duplication are reported but do not fail v0.1's gate.
Missing excerpts show all candidate-missing evidence, including pre-existing gaps.

Entire snapshots/reports are held in memory. Use a small labeled evaluation set;
streaming large corpora, compressed files, and remote URLs are unsupported.
