import argparse
import json
from pathlib import Path
import sys
from .core import InvalidSnapshot, compare, evaluate
from .report import render


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find the evidence your retriever lost.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Evaluate a retrieval snapshot")
    check.add_argument("snapshot")
    check.add_argument("--k", type=int, default=5)
    diff = sub.add_parser("diff", help="Compare snapshots and fail on per-case regressions")
    diff.add_argument("baseline")
    diff.add_argument("candidate")
    diff.add_argument("--k", type=int, default=5)
    diff.add_argument("--max-drop", type=float, default=0.0, help="Allowed per-case drop, fraction 0..1")
    diff.add_argument("--html", help="Write standalone HTML report (contains evidence excerpts)")
    diff.add_argument("--json", dest="json_path", help="Write structured comparison")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            print(json.dumps(evaluate(read(args.snapshot), args.k), ensure_ascii=True, indent=2))
            return 0
        inputs = {Path(args.baseline).resolve(), Path(args.candidate).resolve()}
        outputs = [Path(p).resolve() for p in (args.html, args.json_path) if p]
        if len(set(outputs)) != len(outputs) or inputs.intersection(outputs):
            raise InvalidSnapshot("output paths must be distinct from each other and input snapshots")
        result = compare(read(args.baseline), read(args.candidate), args.k, args.max_drop)
        if args.html:
            write(args.html, render(result))
        if args.json_path:
            write(args.json_path, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(f"Retrieval Delta · evidence coverage @{args.k}")
        for change in result["changes"]:
            state = "FAIL" if change["regressed"] else "PASS"
            print(f"{state:4} {change['id']}: {change['before']['coverage']:.1%} -> "
                  f"{change['after']['coverage']:.1%} ({change['delta'] * 100:+.1f} pp)")
        print(f"{result['regressions']} regression(s); " + ("gate passed" if result['passed'] else "gate failed"))
        return 0 if result['passed'] else 1
    except (InvalidSnapshot, OSError, ValueError) as error:
        print(f"evidiff: {error}", file=sys.stderr)
        return 2
