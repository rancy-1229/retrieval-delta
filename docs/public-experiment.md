# Public-data experiment: smaller context can lose answer spans

This is a deterministic retrieval experiment on SQuAD v1.1 dev, not a benchmark
of generated answers, embedding quality, or production RAG reliability.

## Fixed method

- Corpus: all 2,067 source paragraphs from SQuAD v1.1 dev.
- Questions: sort all 10,570 IDs, sample 300 with Python `Random(20261023)`, then sort again.
- Label: the first annotator's exact answer span. Other annotations are not treated
  as jointly required evidence. This undercounts valid alternative answer locations.
- Baseline: 400-character windows, 80-character overlap.
- Candidate: 200-character windows, 40-character overlap.
- Both: BM25 (k1=1.2, b=0.75), Unicode word tokenization, lowercase, no stemming,
  no stopword removal, query terms deduplicated, top-5. Deterministic tie order.
- Ranking uses only source text and question text; answer labels are not passed to
  the retriever. Paragraphs are independent documents and source identity matters.
- No model/API calls. Configurations fixed before running; no parameter sweep.

## Observed results

| Metric | Baseline | Candidate |
|---|---:|---:|
| Indexed chunks | 5,480 | 10,504 |
| Mean first-answer-span coverage @5 | 88.45% | 78.96% |
| Fully covered questions | 264/300 | 230/300 |
| Mean retrieved characters | 1,791.79 | 936.33 |

39 questions regressed, 3 improved, 258 were unchanged. Context length fell by
47.74%, while coverage fell by 9.49 percentage points. Every one of the 600
per-question scores matched a separate character-set implementation, independent
of Retrieval Delta's interval-merging algorithm.

These results demonstrate an observable tradeoff and a reproducible per-question
diagnosis. They do not show that 400-character chunks are universally better.
The two top-5 configurations have unequal context budgets. Fixed windows can cut
words; this reference BM25 is not a state-of-the-art retriever. The sample was
not used for parameter selection, but no confidence interval or repeated-seed
analysis is claimed. First-answer spans are weaker labels than full supporting
evidence, and answer correctness is never evaluated.

## Reproduce

Download the public file separately, then run from the repository root:

```sh
curl --fail --location https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json -o /tmp/squad-dev-v1.1.json
python -m examples.squad_benchmark --dataset /tmp/squad-dev-v1.1.json --out ./squad-run
```

The script checks dataset SHA-256 before running:

```text
95aa6a52d5d6a735563366753ca50492a658031da74f301ac5238b03966972c9
```

Outputs: full baseline/candidate snapshots, comparison JSON, summary with selected
IDs and settings, standalone HTML, and dataset attribution. The experiment command
exits 0 when it completes (it is not the CI gate); running `evidiff diff` on the
resulting snapshots exits 1 because it finds regressions.

## Dataset attribution

SQuAD by Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev, and Percy Liang.
[Original project](https://rajpurkar.github.io/SQuAD-explorer/),
[paper](https://arxiv.org/abs/1606.05250),
[dataset license declaration](https://huggingface.co/datasets/rajpurkar/squad/blob/main/README.md).
Dataset and derived excerpts are CC BY-SA 4.0
(https://creativecommons.org/licenses/by-sa/4.0/).
The script samples questions, splits passages, and generates retrieval reports;
these are modifications, not original dataset outputs. Project code is MIT.
Downloaded data and generated reports are not bundled into the source archive.
