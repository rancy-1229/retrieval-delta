import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from evidiff.core import InvalidSnapshot, compare, evaluate, subtract, validate
from evidiff.adapters import anchor, from_chunks
from evidiff.report import render
ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return {'version': 1, 'documents': {'d': {'text': 'abcdefghij你好'}}, 'cases': [
        {'id': 'q', 'question': 'Question?', 'evidence': [{'document': 'd', 'start': 2, 'end': 8}],
         'retrieved': [{'document': 'd', 'start': 0, 'end': 5}]}]}


class Metrics(unittest.TestCase):
    def test_hand_calculated_partial(self):
        r = evaluate(fixture())['cases'][0]
        self.assertEqual(r['coverage'], 0.5)
        self.assertEqual(r['missing'][0]['text'], 'fgh')
        self.assertEqual(r['evidence_density'], 3 / 5)

    def test_overlaps_do_not_inflate(self):
        s = fixture(); s['cases'][0]['evidence'] *= 3; s['cases'][0]['retrieved'] *= 2
        r = evaluate(s)['cases'][0]
        self.assertEqual(r['coverage'], 0.5)
        self.assertEqual(r['evidence_chars'], 6)
        self.assertEqual(r['duplicate_context_chars'], 5)
        self.assertEqual(r['evidence_density'], 3 / 10)

    def test_adjacent_chunks_cover_whole_span(self):
        s = fixture(); s['cases'][0]['retrieved'].append({'document': 'd', 'start': 5, 'end': 8})
        self.assertTrue(evaluate(s)['cases'][0]['complete'])
        self.assertEqual(evaluate(s, 1)['cases'][0]['coverage'], 0.5)

    def test_empty_retrieval(self):
        s = fixture(); s['cases'][0]['retrieved'] = []
        self.assertEqual(evaluate(s)['coverage'], 0)

    def test_wrong_document_cannot_match(self):
        s = fixture(); s['documents']['other'] = {'text': 'abcdefghij你好'}
        s['cases'][0]['retrieved'][0]['document'] = 'other'
        self.assertEqual(evaluate(s)['coverage'], 0)

    def test_unicode_offsets(self):
        s = fixture(); s['cases'][0]['evidence'] = [{'document': 'd', 'start': 10, 'end': 12}]
        s['cases'][0]['retrieved'] = [{'document': 'd', 'start': 10, 'end': 11}]
        r = evaluate(s)['cases'][0]
        self.assertEqual(r['coverage'], 0.5); self.assertEqual(r['missing'][0]['text'], '好')

    def test_interval_subtraction_against_set_oracle(self):
        spans = [(a, b) for a in range(6) for b in range(a + 1, 7)]
        for source in spans:
            for a in spans:
                for b in spans:
                    actual = {x for lo, hi in subtract([source], [a, b]) for x in range(lo, hi)}
                    self.assertEqual(actual, set(range(*source)) - set(range(*a)) - set(range(*b)))

    def test_invalid_data(self):
        mutations = [lambda s: s.update(cases=[]), lambda s: s['cases'][0].update(evidence=[]),
                     lambda s: s['cases'][0]['retrieved'][0].update(start=-1),
                     lambda s: s['cases'][0]['retrieved'][0].update(end=999),
                     lambda s: s['cases'][0]['retrieved'][0].update(start=True),
                     lambda s: s['cases'][0]['retrieved'][0].update(text='wrong'),
                     lambda s: s['documents']['d'].update(sha256='stale'),
                     lambda s: s['cases'].append(copy.deepcopy(s['cases'][0]))]
        for mutate in mutations:
            s = fixture(); mutate(s)
            with self.assertRaises(InvalidSnapshot): validate(s)
        for k in [0, -1, True]:
            with self.assertRaises(InvalidSnapshot): evaluate(fixture(), k)

    def test_comparison_refuses_moving_ground_truth(self):
        for mutate in [lambda s: s['documents']['d'].update(text='changed'),
                       lambda s: s['cases'][0].update(id='different'),
                       lambda s: s['cases'][0].update(question='changed'),
                       lambda s: s['cases'][0]['evidence'][0].update(end=9)]:
            a = fixture(); b = copy.deepcopy(a); mutate(b)
            with self.assertRaises(InvalidSnapshot): compare(a, b)

    def test_tolerance_boundary(self):
        a = fixture(); b = copy.deepcopy(a); b['cases'][0]['retrieved'] = []
        self.assertFalse(compare(a, b)['passed']); self.assertTrue(compare(a, b, max_drop=0.5)['passed'])
        for value in [float('nan'), float('inf'), -0.1, 1.1, True]:
            with self.assertRaises(InvalidSnapshot): compare(a, b, max_drop=value)

    def test_improvement_cannot_hide_regression(self):
        a = fixture(); a['cases'].append(copy.deepcopy(a['cases'][0])); a['cases'][1]['id'] = 'q2'
        a['cases'][1]['retrieved'] = []
        b = copy.deepcopy(a); b['cases'][0]['retrieved'] = []
        b['cases'][1]['retrieved'] = copy.deepcopy(b['cases'][1]['evidence'])
        r = compare(a, b)
        self.assertGreater(r['candidate']['coverage'], r['baseline']['coverage'])
        self.assertFalse(r['passed'])

    def test_html_escapes_untrusted_source(self):
        a = fixture(); a['cases'][0]['question'] = '<script>alert(1)</script>'
        html = render(compare(a, a))
        self.assertNotIn('<script>', html); self.assertIn('&lt;script&gt;', html)

    def test_anchor_refuses_ambiguous_or_modified_chunks(self):
        for text in ['aa', 'absent', '']:
            with self.assertRaises(InvalidSnapshot): anchor({'d': 'aaaa'}, 'd', text)
        self.assertEqual(anchor({'d': '你好世界'}, 'd', '世界')['start'], 2)

    def test_plain_text_adapter(self):
        s = from_chunks({'d': 'hello world'}, [{'id': 'q', 'question': 'What?',
                        'evidence': [{'document': 'd', 'text': 'world'}],
                        'retrieved': [{'document': 'd', 'text': 'hello world'}]}])
        self.assertEqual(evaluate(s)['coverage'], 1)


class CLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'evidiff', *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True)

    def test_examples_fail_then_pass_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.html'; data = Path(directory) / 'report.json'
            r = self.run_cli('diff', 'examples/baseline.json', 'examples/candidate.json',
                             '--html', report, '--json', data)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertEqual(json.loads(data.read_text())['regressions'], 2)
            self.assertIn('not refundable', report.read_text())
            r = self.run_cli('diff', 'examples/baseline.json', 'examples/fixed.json')
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_actual_retriever_export_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / 'examples/retriever_demo.py'),
                                     '--out', directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(directory) / 'result.json'
            result = self.run_cli('diff', Path(directory) / 'sentences.json',
                                  Path(directory) / 'fixed.json', '--k', '1', '--json', output)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(output.read_text())['regressions'], 3)

    def test_malformed_json_exits_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'; path.write_text('{')
            self.assertEqual(self.run_cli('check', path).returncode, 2)

    def test_output_cannot_overwrite_input(self):
        r = self.run_cli('diff', 'examples/baseline.json', 'examples/candidate.json',
                         '--html', 'examples/baseline.json')
        self.assertEqual(r.returncode, 2); self.assertIn('output paths', r.stderr)


if __name__ == '__main__': unittest.main()
