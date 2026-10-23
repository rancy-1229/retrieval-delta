# Retrieval Delta

Public project name: **Retrieval Delta** (`retrieval-delta`). The Python module
remains `evidiff`; both `retrieval-delta` and `evidiff` CLI commands work.
Source: [rancy-1229/retrieval-delta](https://github.com/rancy-1229/retrieval-delta).
The package is not published to PyPI; install from source below.

**Find the evidence your retriever lost.**

Change your chunker, embedding model, or reranker. Export both retrieval runs.
Retrieval Delta shows exactly which labeled source passages disappeared — and fails CI
when a single question regresses, even if your average score improves.

**Offline. No API key. No runtime dependencies. Python 3.10+.**

> Early release / v0.1.0.
> The bundled four-question example is a synthetic demonstration, not a benchmark.

[中文说明](README.zh-CN.md) · [Snapshot format](docs/format.md) · [Contributing](CONTRIBUTING.md)

## Try it locally

Clone the repository and enter its directory:

```sh
git clone https://github.com/rancy-1229/retrieval-delta.git
cd retrieval-delta
```

Run directly from source:

```sh
python -m evidiff diff examples/baseline.json examples/candidate.json \
  --html report.html --json report.json
```

Expected output (exit code **1**, intentionally):

```text
Retrieval Delta · evidence coverage @5
FAIL custom-refund: 100.0% -> 0.0% (-100.0 pp)
FAIL damage-window: 100.0% -> 63.8% (-36.2 pp)
PASS support-hours: 100.0% -> 100.0% (+0.0 pp)
PASS international-delivery: 0.0% -> 100.0% (+100.0 pp)
2 regression(s); gate failed
```

Open `report.html` in a browser. It shows missing source excerpts, per-question
coverage, context size, and duplicate context. It is a standalone file with no
JavaScript or external resources.

Then try the repaired retrieval results:

```sh
python -m evidiff diff examples/baseline.json examples/fixed.json
# Exit 0: no question regressed.
```

For an installed CLI, use `python -m pip install .`, then `retrieval-delta diff ...`.
No public `pip install evidiff` package is claimed by this project yet.

## Run a real retrieval comparison

The fixture above is hand-authored. This second demo actually chunks and ranks
the same synthetic corpus using lexical overlap:

```sh
python examples/retriever_demo.py --out ./demo-run
python -m evidiff diff demo-run/sentences.json demo-run/fixed.json --k 1 --html demo-run/report.html
```

It compares line/sentence chunks with 40-character chunks. Expected: three
regressions (exit 1). It tests the export → retrieval → diff path, not embedding
quality or production performance. No API key or network is needed.

## Public-data experiment

On 300 fixed-seed SQuAD questions, reducing chunk size shortened retrieved context
by 47.74%, while 39 questions lost answer-span coverage and 3 improved. This is
a lexical retrieval experiment, not generated-answer evaluation. See
[method, limitations, attribution, and reproduction](docs/public-experiment.md).

## Connect your retriever

Keep the source documents and human-selected evidence fixed; replace only the
ranked `retrieved` list between runs. Chunk IDs may change freely.

```python
import json
from evidiff.adapters import from_chunks

documents = {"policy": "Standard returns: 30 days. Custom items are not refundable."}
snapshot = from_chunks(documents, [{
    "id": "custom-refund",
    "question": "Can I return a custom item?",
    "evidence": [{"document": "policy", "text": "Custom items are not refundable."}],
    "retrieved": [{"document": "policy", "text": "Standard returns: 30 days."}],
}])
with open("candidate.json", "w", encoding="utf-8") as stream:
    json.dump(snapshot, stream, ensure_ascii=False, indent=2)
```

Map vector-store result text and document IDs into those dictionaries. The adapter
anchors **unique exact substrings**. Repeated passages, OCR normalization, or
synthetically enriched chunks need explicit offsets into a canonical source;
Retrieval Delta refuses to guess. This is a plain-text adapter, not a tested integration
with every vector database.

## What the numbers mean

- **Evidence coverage @ k:** union of labeled source characters present in the
  top-k retrieved spans, divided by union of all labeled evidence characters.
- **Complete case:** all labeled evidence characters are present.
- **Evidence density:** covered gold characters / total submitted context
  characters. Duplicate retrieved spans still cost context.
- **Duplicate context:** submitted characters minus unique source characters.
- **Gate:** any per-case coverage drop larger than `--max-drop` fails. Default is
  zero; `--max-drop 0.05` tolerates a five-percentage-point drop.

Different document text, question sets, or gold evidence cause an input error;
rebaseline intentionally rather than comparing different tasks.

Character coverage is diagnostic, **not semantic correctness**. Losing a single
negation can be serious despite high coverage. Complete coverage does not prove
the model used the evidence or produced a correct answer. Multi-hop gold spans
are treated as jointly required; alternative sufficient evidence sets and
unanswerable questions are not implemented. Context size is characters, not tokens.

## CI

Use an installed/pinned checkout of this project:

```sh
python -m evidiff diff baseline.json candidate.json --html report.html --json report.json
```

Exit codes: **0** no regression; **1** regression; **2** invalid input or I/O error.
`check snapshot.json` validates and scores a snapshot without applying a gate.
Reports contain source excerpts: review them before publishing CI artifacts.

The repository's test workflow covers Python 3.10/3.12/3.13 on Linux, Windows,
and macOS when run on GitHub; only the local environment has been verified so far.

## Why another retrieval tool?

[Ragas](https://github.com/vibrantlabsai/ragas),
[DeepEval](https://github.com/confident-ai/deepeval), and
[Promptfoo](https://github.com/promptfoo/promptfoo) provide broader evaluation
workflows. Retrieval Delta focuses on a small source-span diff and per-question CI gate,
without running a model or prescribing a retrieval framework. Deterministic
retrieval metrics and span coverage are existing ideas, not an invention here.

## Development

```sh
python -m unittest discover -s tests -v
```

MIT licensed. No telemetry. Inputs are read locally; no model or database is called.
