"""Extract operative rule text from ARCP PDFs, stripping non-rule content."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pdfplumber

PDF_DIR = Path(__file__).resolve().parent.parent / "data" / "arcp" / "pdfs"
TEXT_DIR = Path(__file__).resolve().parent.parent / "data" / "arcp" / "text"
COMBINED_PATH = Path(__file__).resolve().parent.parent / "data" / "arcp" / "arcp_combined.txt"

# Boundary patterns — the first match marks the end of operative rule text.
# Everything from this line onward is stripped.
BOUNDARY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Committee\s+Comments?", re.IGNORECASE),
    re.compile(r"^Advisory\s+Committee", re.IGNORECASE),
    re.compile(r"^Reporter'?s?\s+Notes?", re.IGNORECASE),
    re.compile(r"^Note\s+from\s+(the\s+)?reporter", re.IGNORECASE),
    re.compile(r"^Authors?'?s?\s+Comments?", re.IGNORECASE),
    re.compile(r"^Amendment\s+(history|effective)", re.IGNORECASE),
    re.compile(r"^History\s+of\s+amendments?", re.IGNORECASE),
    re.compile(r"^Amendments?\s+to\s+(this\s+)?rule", re.IGNORECASE),
    re.compile(r"^Notes?\s+of\s+decisions", re.IGNORECASE),
    re.compile(r"^District\s+Court\s+Committee", re.IGNORECASE),
    # Amendment history block: "[Amended eff. ..." or "[Amended 10-14-76"
    re.compile(r"^\[Amended\s", re.IGNORECASE),
]

# Page header/footer patterns to strip line by line.
PAGE_HEADER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*Alabama\s+Rules?\s+of\s+Civil\s+Procedure\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # Standalone page numbers
    re.compile(r"^\s*Page\s+\d+\s+of\s+\d+", re.IGNORECASE),
    re.compile(r"^\f"),  # Form feed characters
]


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber."""
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def find_rule_title(lines: list[str]) -> str:
    """Extract the rule title from the first few lines.

    Handles two formats:
      - Single line: "Rule 6. Time."
      - Two lines: "Rule 6." followed by "Time."
    """
    for i, line in enumerate(lines[:15]):
        stripped = line.strip()

        # Single-line: "Rule 6. Time."
        match = re.match(
            r"^Rule\s+(\d+[A-Za-z]?)\.\s+(.+?)\.?\s*$", stripped, re.IGNORECASE
        )
        if match:
            return f"Rule {match.group(1)}. {match.group(2).strip().rstrip('.')}."

        # Two-line: "Rule 6." on this line, title on next
        match = re.match(r"^Rule\s+(\d+[A-Za-z]?)\.\s*$", stripped, re.IGNORECASE)
        if match and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not next_line.startswith("("):
                title_text = next_line.rstrip(".")
                return f"Rule {match.group(1)}. {title_text}."

    return ""


def is_boundary_line(line: str) -> bool:
    """Check if a line marks the end of operative rule text."""
    stripped = line.strip()
    return any(pat.match(stripped) for pat in BOUNDARY_PATTERNS)


def is_page_header(line: str) -> bool:
    """Check if a line is a page header/footer to remove."""
    return any(pat.match(line) for pat in PAGE_HEADER_PATTERNS)


def clean_rule_text(raw_text: str) -> tuple[str, str]:
    """Clean extracted text to keep only operative rule content.

    Strategy: find the first boundary marker (committee comments, amendment
    history, reporter notes) and keep only lines before it. Then strip page
    headers/footers and clean up whitespace.

    Returns:
        Tuple of (rule_title, cleaned_text).
    """
    lines = raw_text.split("\n")
    title = find_rule_title(lines)

    # Find the first boundary line — everything from here onward is non-rule.
    cut_index = len(lines)
    for i, line in enumerate(lines):
        if is_boundary_line(line):
            cut_index = i
            break

    # Keep only operative text (before the boundary).
    kept = lines[:cut_index]

    # Strip page headers/footers and leading section headers (e.g. "II. PLEADINGS").
    cleaned: list[str] = []
    found_rule_start = False
    for line in kept:
        stripped = line.strip()

        # Skip blank lines before content starts.
        if not found_rule_start and not stripped:
            continue

        # Skip page headers.
        if is_page_header(line):
            continue

        # Skip everything before the "Rule XX." line — this catches
        # Roman-numeral section headers (e.g. "II. PLEADINGS AND MOTIONS")
        # and their continuation lines (e.g. "and orders.") that appear
        # before the rule number.
        if not found_rule_start:
            if re.match(r"^Rule\s+\d+", stripped, re.IGNORECASE):
                found_rule_start = True
            else:
                continue

        # (found_rule_start is True from here on)
        cleaned.append(line)

    # Trim trailing blank lines.
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    # Trim leading blank lines.
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)

    # Collapse runs of 3+ blank lines to 2.
    result: list[str] = []
    blank_count = 0
    for line in cleaned:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    return title, "\n".join(result)


def rule_sort_key(filename: str) -> tuple[int, str]:
    """Sort key for rule filenames — numeric then alpha suffix."""
    match = re.match(r"cv(\d+)([A-Za-z]?)\.pdf", filename, re.IGNORECASE)
    if match:
        return (int(match.group(1)), match.group(2))
    return (999, filename)


def extract_rule_number(filename: str) -> str:
    """Extract rule number from filename like 'cv7A.pdf' -> '7A'."""
    match = re.match(r"cv(\d+[A-Za-z]?)\.pdf", filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return filename.replace(".pdf", "")


def process_all_pdfs() -> None:
    """Process all downloaded PDFs and extract rule text."""
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(PDF_DIR.glob("cv*.pdf"), key=lambda p: rule_sort_key(p.name))
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIR}")
        sys.exit(1)

    print(f"Processing {len(pdf_files)} PDFs from {PDF_DIR}/\n")

    summaries: list[tuple[str, str, int]] = []
    combined_parts: list[str] = []

    for pdf_path in pdf_files:
        rule_num = extract_rule_number(pdf_path.name)
        print(f"  Processing {pdf_path.name} ... ", end="", flush=True)

        try:
            raw_text = extract_text_from_pdf(pdf_path)
            title, cleaned = clean_rule_text(raw_text)

            # Write individual rule file.
            out_name = f"rule_{rule_num}.txt"
            out_path = TEXT_DIR / out_name
            out_path.write_text(cleaned, encoding="utf-8")

            word_count = len(cleaned.split())
            display_title = title or f"Rule {rule_num}"
            summaries.append((rule_num, display_title, word_count))
            print(f"OK  {display_title} ({word_count:,} words)")

            # Append to combined text.
            separator = "=" * 72
            combined_parts.append(f"{separator}\n{display_title}\n{separator}\n\n{cleaned}\n")

        except Exception as exc:
            print(f"FAILED ({exc})")
            summaries.append((rule_num, f"Rule {rule_num} (FAILED)", 0))

    # Write combined file.
    COMBINED_PATH.write_text("\n\n".join(combined_parts), encoding="utf-8")

    # Print summary.
    print(f"\n{'─' * 60}")
    print(f"{'Rule':<10} {'Title':<40} {'Words':>8}")
    print(f"{'─' * 60}")
    total_words = 0
    for rule_num, title, wc in summaries:
        short_title = title[:38] + ".." if len(title) > 40 else title
        print(f"{rule_num:<10} {short_title:<40} {wc:>8,}")
        total_words += wc
    print(f"{'─' * 60}")
    print(f"{'TOTAL':<10} {len(summaries)} rules{'':<29} {total_words:>8,}")
    print(f"\nOutput: {TEXT_DIR}/")
    print(f"Combined: {COMBINED_PATH}")


if __name__ == "__main__":
    process_all_pdfs()
