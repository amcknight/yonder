"""yonder CLI: `extract` one PDF, `eval` a folder of labeled PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from yonder.eval.score import FieldResult, ResultType, score_extract, tally
from yonder.extract.client import ClaudeClient
from yonder.extract.schema import StrataExtract
from yonder.extract.strata import extract_strata

_SYMBOL = {
    ResultType.MATCH: "OK ",
    ResultType.WRONG: "XX ",
    ResultType.MISSED: "-- ",
    ResultType.UNLABELED_EXTRA: "?? ",
    ResultType.HALLUCINATION: "!! ",
}


def render_report(doc_name: str, results: list[FieldResult], *, complete: bool) -> str:
    lines = [f"doc: {doc_name}  (label: {'complete' if complete else 'partial'})"]
    for r in results:
        detail = ""
        if r.type == ResultType.WRONG:
            detail = f"  got {r.got!r}, expected {r.expected!r}"
        elif r.expected:
            detail = f"  {r.expected}"
        elif r.got:
            detail = f"  {r.got}"
        lines.append(f"  {_SYMBOL[r.type]}{r.field}{detail}")
    counts = tally(results)
    summary = "  ".join(f"{t.value}: {counts[t]}" for t in ResultType if counts[t])
    lines.append(f"  counts -> {summary or 'none'}")
    if not complete:
        lines.append("  (label partial: extras are unknown, NOT counted as hallucinations)")
    return "\n".join(lines)


def _build_client() -> ClaudeClient:
    return ClaudeClient()


def cmd_extract(args: argparse.Namespace) -> int:
    pdf_bytes = Path(args.pdf).read_bytes()
    extract = extract_strata(pdf_bytes, client=_build_client())
    print(json.dumps(extract.model_dump(mode="json"), indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {folder}", file=sys.stderr)
        return 1
    client = _build_client()
    for pdf in pdfs:
        label_path = pdf.with_suffix(".expected.json")
        if not label_path.exists():
            # Convention: the sample uses expected.json (single sample per folder).
            alt = pdf.parent / "expected.json"
            label_path = alt if alt.exists() else label_path
        if not label_path.exists():
            print(f"skip {pdf.name}: no label", file=sys.stderr)
            continue
        label = json.loads(label_path.read_text())
        extract = extract_strata(pdf.read_bytes(), client=client)
        results = score_extract(extract, label)
        print(render_report(pdf.stem, results, complete=bool(label.get("complete", False))))
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yonder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract facts from one strata PDF.")
    p_extract.add_argument("pdf")
    p_extract.set_defaults(func=cmd_extract)

    p_eval = sub.add_parser("eval", help="Score labeled PDFs in a folder.")
    p_eval.add_argument("folder")
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
