"""Reproducible public-data retrieval experiment (not an answer-quality benchmark).

Run from repository root: python -m examples.squad_benchmark --dataset PATH --out DIR
Download the dataset separately; this script never accesses the network.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
from evidiff.core import compare, digest
from evidiff.report import render

DATASET_URL = 'https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json'
EXPECTED_SHA256 = '95aa6a52d5d6a735563366753ca50492a658031da74f301ac5238b03966972c9'


def tokenize(text):
    return re.findall(r'\w+', text.lower())


def load_corpus(data):
    documents, questions = {}, []
    for ai, article in enumerate(data['data']):
        for pi, paragraph in enumerate(article['paragraphs']):
            did = f'{ai}:{pi}'
            source = paragraph['context']
            documents[did] = {'text': source, 'title': article['title'], 'sha256': digest(source)}
            for question in paragraph['qas']:
                # Deliberately use one annotator; do not require alternative answers jointly.
                answer = question['answers'][0]
                start, text = answer['answer_start'], answer['text']
                if source[start:start + len(text)] != text:
                    raise ValueError(f"invalid source annotation: {question['id']}")
                questions.append({'id': question['id'], 'question': question['question'],
                                  'evidence': [{'document': did, 'start': start,
                                                'end': start + len(text), 'text': text}]})
    return documents, questions


class BM25:
    """Simple lexical reference retriever. k1=1.2, b=.75, no stemming/stopwords."""
    def __init__(self, documents, size, overlap):
        if not 0 <= overlap < size:
            raise ValueError('need 0 <= overlap < size')
        self.chunks, lengths, postings = [], [], defaultdict(list)
        for did, document in documents.items():
            source = document['text']
            start = 0
            while start < len(source):
                end = min(start + size, len(source))
                index = len(self.chunks)
                self.chunks.append({'document': did, 'start': start, 'end': end})
                counts = Counter(tokenize(source[start:end]))
                lengths.append(sum(counts.values()))
                for token, count in counts.items():
                    postings[token].append((index, count))
                if end == len(source):
                    break
                start += size - overlap
        average = sum(lengths) / len(lengths)
        self.weights = {}
        for token, hits in postings.items():
            idf = math.log(1 + (len(lengths) - len(hits) + .5) / (len(hits) + .5))
            self.weights[token] = [(i, idf * tf * 2.2 /
                                    (tf + 1.2 * (.25 + .75 * lengths[i] / average)))
                                   for i, tf in hits]

    def retrieve(self, question, k):
        scores = defaultdict(float)
        for token in sorted(set(tokenize(question))):
            for index, score in self.weights.get(token, []):
                scores[index] += score
        return [self.chunks[i] for i in sorted(scores, key=lambda i: (-scores[i], i))[:k]]


def oracle(snapshot, k):
    """Independent character-set check; intentionally does not use interval helpers."""
    scores = {}
    for case in snapshot['cases']:
        gold = {(s['document'], i) for s in case['evidence'] for i in range(s['start'], s['end'])}
        got = {(s['document'], i) for s in case['retrieved'][:k] for i in range(s['start'], s['end'])}
        scores[case['id']] = len(gold & got) / len(gold)
    return scores


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    raw = args.dataset.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SHA256:
        parser.error('dataset hash mismatch; this experiment requires the documented SQuAD v1.1 dev file')
    documents, questions = load_corpus(json.loads(raw))
    selected = sorted(random.Random(20261023).sample(sorted(questions, key=lambda q: q['id']), 300),
                      key=lambda q: q['id'])
    configs = [('baseline', 400, 80), ('candidate', 200, 40)]
    snapshots, chunk_counts = {}, {}
    for name, size, overlap in configs:
        retriever = BM25(documents, size, overlap)
        chunk_counts[name] = len(retriever.chunks)
        snapshots[name] = {'version': 1, 'documents': documents,
                           'cases': [dict(q, retrieved=retriever.retrieve(q['question'], 5))
                                     for q in selected]}
    result = compare(snapshots['baseline'], snapshots['candidate'], k=5)
    for name in ('baseline', 'candidate'):
        independent = oracle(snapshots[name], 5)
        for case in result[name]['cases']:
            if abs(independent[case['id']] - case['coverage']) > 1e-12:
                raise AssertionError(f'oracle disagreement: {name}/{case["id"]}')
    summary = {'dataset_url': DATASET_URL, 'dataset_sha256': sha,
               'dataset_license': 'CC-BY-SA-4.0', 'dataset_authors': 'Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev, Percy Liang',
               'sample_seed': 20261023, 'sample_size': len(selected), 'corpus_documents': len(documents),
               'total_available_questions': len(questions), 'sample_ids': [q['id'] for q in selected],
               'metric_scope': 'First-annotator answer-span coverage, not supporting-evidence or answer correctness',
               'configs': {name: {'size_characters': size, 'overlap_characters': overlap,
                                  'chunks': chunk_counts[name], 'k': 5} for name, size, overlap in configs},
               'regressions': result['regressions'],
               'improvements': sum(c['delta'] > 1e-12 for c in result['changes']),
               'unchanged': sum(abs(c['delta']) <= 1e-12 for c in result['changes']),
               'independent_set_oracle': 'all 600 per-case coverage values matched',
               **{name: {'mean_answer_span_coverage': result[name]['coverage'],
                         'complete_cases': result[name]['complete_cases'],
                         'mean_context_characters': sum(c['context_chars'] for c in result[name]['cases']) / len(selected)}
                  for name in ('baseline', 'candidate')}}
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in [*snapshots.items(), ('comparison', result), ('summary', summary)]:
        (args.out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    html = render(result).replace('<title>Retrieval Delta', '<title>SQuAD answer-span experiment · Retrieval Delta')
    html = html.replace('<h1>', '<p>SQuAD v1.1 · 300 sampled questions · first-annotator answer spans, not full supporting evidence. '
                        'Dataset by Rajpurkar et al.; CC BY-SA 4.0. Source excerpts adapted into a retrieval report.</p><h1>', 1)
    (args.out / 'report.html').write_text(html, encoding='utf-8')
    (args.out / 'ATTRIBUTION.md').write_text(
        '# Dataset attribution\n\nSQuAD v1.1 by Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev, Percy Liang.\n'
        f'Source: {DATASET_URL}\n\nDataset and derived excerpts: CC BY-SA 4.0 '
        '(https://creativecommons.org/licenses/by-sa/4.0/).\n'
        'Changes: sampled questions, split source passages, performed lexical retrieval, generated coverage reports.\n'
        'Project code remains MIT licensed. No endorsement by dataset authors is implied.\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in summary.items() if key != 'sample_ids'}, indent=2))


if __name__ == '__main__':
    main()
