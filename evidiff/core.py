"""Offsets are Python Unicode character offsets, half-open [start, end).

Gold spans are unioned per document, so duplicate/overlapping annotations never
inflate coverage. Retrieved context is clipped to the requested top-k first.
"""
import hashlib
import math


class InvalidSnapshot(ValueError):
    pass


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def merge(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def subtract(source, covered):
    missing = []
    for start, end in merge(source):
        cursor = start
        for left, right in merge(covered):
            if right <= cursor or left >= end:
                continue
            if left > cursor:
                missing.append((cursor, left))
            cursor = max(cursor, min(end, right))
        if cursor < end:
            missing.append((cursor, end))
    return missing


def _require(condition, message):
    if not condition:
        raise InvalidSnapshot(message)


def validate(snapshot):
    _require(isinstance(snapshot, dict), "snapshot must be an object")
    _require(type(snapshot.get("version")) is int and snapshot["version"] == 1,
             "version must be 1")
    docs = snapshot.get("documents")
    cases = snapshot.get("cases")
    _require(isinstance(docs, dict) and bool(docs), "documents must be a nonempty object")
    _require(isinstance(cases, list) and bool(cases), "cases must be a nonempty list")
    for doc_id, doc in docs.items():
        _require(isinstance(doc_id, str) and bool(doc_id), "document IDs must be nonempty strings")
        _require(isinstance(doc, dict) and isinstance(doc.get("text"), str),
                 f"document {doc_id}: text must be a string")
        if "sha256" in doc:
            _require(doc["sha256"] == digest(doc["text"]), f"document {doc_id}: stale sha256")
    ids = set()
    for case in cases:
        _require(isinstance(case, dict), "each case must be an object")
        cid = case.get("id")
        _require(isinstance(cid, str) and bool(cid), "case id must be a nonempty string")
        _require(cid not in ids, f"duplicate case id: {cid}")
        ids.add(cid)
        _require(isinstance(case.get("question"), str) and bool(case["question"]),
                 f"{cid}: question must be a nonempty string")
        for field in ("evidence", "retrieved"):
            spans = case.get(field)
            _require(isinstance(spans, list), f"{cid}: {field} must be a list")
            if field == "evidence":
                _require(bool(spans), f"{cid}: evidence must not be empty; no-answer cases unsupported")
            for span in spans:
                _require(isinstance(span, dict), f"{cid}: span must be an object")
                did = span.get("document")
                _require(isinstance(did, str) and did in docs, f"{cid}: unknown document {did!r}")
                start, end = span.get("start"), span.get("end")
                _require(type(start) is int and type(end) is int,
                         f"{cid}: offsets must be integers")
                _require(0 <= start < end <= len(docs[did]["text"]), f"{cid}: invalid span bounds")
                if "text" in span:
                    _require(span["text"] == docs[did]["text"][start:end],
                             f"{cid}: span text does not match source offsets")
    return snapshot


def _group(spans):
    groups = {}
    for span in spans:
        groups.setdefault(span["document"], []).append((span["start"], span["end"]))
    return {key: merge(value) for key, value in groups.items()}


def _length(group):
    return sum(end - start for spans in group.values() for start, end in spans)


def evaluate(snapshot, k=5):
    validate(snapshot)
    _require(type(k) is int and k > 0, "k must be a positive integer")
    results = []
    for case in snapshot["cases"]:
        gold = _group(case["evidence"])
        retrieved = case["retrieved"][:k]
        context = _group(retrieved)
        missing = {doc: subtract(spans, context.get(doc, [])) for doc, spans in gold.items()}
        total = _length(gold)
        hit = total - _length(missing)
        sent_chars = sum(s["end"] - s["start"] for s in retrieved)
        missing_details = [{"document": doc, "start": a, "end": b,
                            "text": snapshot["documents"][doc]["text"][a:b]}
                           for doc, spans in missing.items() for a, b in spans]
        results.append({"id": case["id"], "question": case["question"],
                        "coverage": hit / total, "covered_chars": hit, "evidence_chars": total,
                        "complete": hit == total, "context_chars": sent_chars,
                        "evidence_density": hit / sent_chars if sent_chars else 0.0,
                        "duplicate_context_chars": sent_chars - _length(context),
                        "missing": missing_details})
    return {"k": k, "coverage": sum(r["coverage"] for r in results) / len(results),
            "complete_cases": sum(r["complete"] for r in results), "cases": results}


def _gold_signature(case):
    return case["question"], _group(case["evidence"])


def compare(before, after, k=5, max_drop=0.0):
    _require(isinstance(max_drop, (int, float)) and not isinstance(max_drop, bool)
             and math.isfinite(max_drop) and 0 <= max_drop <= 1,
             "max_drop must be a finite fraction between 0 and 1")
    baseline, candidate = evaluate(before, k), evaluate(after, k)
    _require(set(before["documents"]) == set(after["documents"]),
             "document set changed; create a new baseline")
    for doc in before["documents"]:
        _require(before["documents"][doc]["text"] == after["documents"][doc]["text"],
                 f"source changed: {doc}; re-label evidence and create a new baseline")
    old_cases = {c["id"]: c for c in before["cases"]}
    new_cases = {c["id"]: c for c in after["cases"]}
    _require(set(old_cases) == set(new_cases), "case set changed; missing/new cases cannot silently pass")
    for cid in old_cases:
        _require(_gold_signature(old_cases[cid]) == _gold_signature(new_cases[cid]),
                 f"gold evidence or question changed: {cid}; create a new baseline")
    old_scores = {r["id"]: r for r in baseline["cases"]}
    changes = []
    for new in candidate["cases"]:
        old = old_scores[new["id"]]
        delta = new["coverage"] - old["coverage"]
        changes.append({"id": new["id"], "question": new["question"],
                        "before": old, "after": new, "delta": delta,
                        "regressed": delta < -max_drop - 1e-12})
    changes.sort(key=lambda c: (c["delta"], c["id"]))
    return {"version": 1, "k": k, "max_drop": max_drop,
            "passed": not any(c["regressed"] for c in changes),
            "regressions": sum(c["regressed"] for c in changes),
            "baseline": baseline, "candidate": candidate, "changes": changes}
