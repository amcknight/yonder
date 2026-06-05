"""yonder CLI: `extract` one PDF, `eval` a folder of labeled PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from yonder.eval.score import FieldResult, ResultType, score_extract, tally
from yonder.extract.client import ClaudeClient
from yonder.extract.strata import extract_strata
from yonder.outlook.sample import wexford_sample

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


def _resolve_label(pdf: Path) -> Path | None:
    """Find a PDF's label: a sibling `<stem>.expected.json`, else an
    `expected.json` in the same folder. Returns None if neither exists."""
    sibling = pdf.with_suffix(".expected.json")
    if sibling.exists():
        return sibling
    folder_label = pdf.parent / "expected.json"
    if folder_label.exists():
        return folder_label
    return None


def find_labeled_pdfs(folder: Path) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Recursively discover PDFs under `folder` (real strata packages nest docs
    in subfolders). Returns (labeled (pdf, label) pairs, unlabeled pdfs)."""
    labeled: list[tuple[Path, Path]] = []
    unlabeled: list[Path] = []
    for pdf in sorted(folder.rglob("*.pdf")):
        label = _resolve_label(pdf)
        if label is not None:
            labeled.append((pdf, label))
        else:
            unlabeled.append(pdf)
    return labeled, unlabeled


def cmd_eval(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    labeled, unlabeled = find_labeled_pdfs(folder)
    if not labeled and not unlabeled:
        print(f"No PDFs under {folder}", file=sys.stderr)
        return 1
    if not labeled:
        print(
            f"No labeled PDFs under {folder} ({len(unlabeled)} found, but none have a "
            "*.expected.json label). Write a label next to a PDF to score it.",
            file=sys.stderr,
        )
        return 1
    client = _build_client()
    for pdf, label_path in labeled:
        label = json.loads(label_path.read_text())
        extract = extract_strata(pdf.read_bytes(), client=client)
        results = score_extract(extract, label)
        print(render_report(pdf.stem, results, complete=bool(label.get("complete", False))))
        print()
    if unlabeled:
        print(f"(skipped {len(unlabeled)} unlabeled PDF(s))", file=sys.stderr)
    return 0


def cmd_outlook_sample(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(wexford_sample().model_dump_json(indent=2))
    print(f"wrote {out}")
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

    p_sample = sub.add_parser(
        "outlook-sample", help="Write the synthetic ReserveOutlook sample JSON."
    )
    p_sample.add_argument(
        "out", nargs="?", default="fixtures/samples/reserve_outlook.sample.json"
    )
    p_sample.set_defaults(func=cmd_outlook_sample)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
