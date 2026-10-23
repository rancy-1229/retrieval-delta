"""Run two actual lexical retrieval pipelines on the synthetic example corpus.

Usage from repository root: python examples/retriever_demo.py --out /tmp/evidiff-run
No model calls. Sentence chunks versus 40-character chunks, top-1 lexical overlap.
This deliberately tiny experiment is a mechanics demo, not a quality benchmark.
"""
import argparse
import json
from pathlib import Path
import re


def tokens(text):
    return set(re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', text.lower()))


def retrieve(documents, question, mode):
    chunks = []
    for did, document in documents.items():
        text = document['text']
        spans = ([(m.start(), m.end()) for m in re.finditer(r'[^\n]+', text)]
                 if mode == 'sentences' else
                 [(a, min(a + 40, len(text))) for a in range(0, len(text), 40)])
        for a, b in spans:
            chunks.append({'document': did, 'start': a, 'end': b, 'text': text[a:b]})
    # Stable input order breaks ties; no framework or vector database involved.
    ranked = sorted(chunks, key=lambda c: -len(tokens(question) & tokens(c['text'])))
    return ranked[:1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    seed = json.loads((Path(__file__).parent / 'baseline.json').read_text(encoding='utf-8'))
    args.out.mkdir(parents=True, exist_ok=True)
    for mode in ['sentences', 'fixed']:
        snapshot = json.loads(json.dumps(seed))
        for case in snapshot['cases']:
            case['retrieved'] = retrieve(snapshot['documents'], case['question'], mode)
        path = args.out / (mode + '.json')
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        print(path)


if __name__ == '__main__': main()
