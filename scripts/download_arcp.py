"""Download Alabama Rules of Civil Procedure PDFs from judicial.alabama.gov."""
from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://judicial.alabama.gov/docs/library/rules/"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "arcp" / "pdfs"

# All 42 ARCP PDFs — filenames are case-sensitive as they appear on the server.
PDF_FILES: list[str] = [
    "cv3.pdf",
    "cv4.pdf",
    "cv5.pdf",
    "cv6.pdf",
    "cv7.pdf",
    "cv8.pdf",
    "cv9.pdf",
    "cv10.pdf",
    "cv11.pdf",
    "cv12.pdf",
    "cv13.pdf",
    "cv14.pdf",
    "cv15.pdf",
    "cv16.pdf",
    "cv17.pdf",
    "cv18.pdf",
    "cv19.pdf",
    "cv20.pdf",
    "cv21.pdf",
    "cv22.pdf",
    "cv23.pdf",
    "cv24.pdf",
    "cv25.pdf",
    "cv26.pdf",
    "cv27.pdf",
    "cv30.pdf",
    "cv33.pdf",
    "cv34.pdf",
    "cv36.pdf",
    "cv37.pdf",
    "cv38.pdf",
    "cv41.pdf",
    "cv45.pdf",
    "cv47.pdf",
    "cv50.pdf",
    "cv51.pdf",
    "cv52.pdf",
    "cv55.pdf",
    "cv56.pdf",
    "cv59.pdf",
    "cv68.pdf",
]


def download_pdfs() -> None:
    """Download all ARCP PDFs, skipping files that already exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed: list[str] = []

    for filename in PDF_FILES:
        dest = OUTPUT_DIR / filename
        if dest.exists() and dest.stat().st_size > 0:
            skipped += 1
            print(f"  [skip] {filename} (already exists)")
            continue

        url = BASE_URL + filename
        print(f"  [GET]  {url} ... ", end="", flush=True)

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/17.0 Safari/605.1.15"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"OK ({size_kb:.0f} KB)")
            downloaded += 1
        except Exception as exc:
            print(f"FAILED ({exc})")
            failed.append(filename)

        # Be polite to the server.
        time.sleep(0.5)

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped, {len(failed)} failed")
    if failed:
        print(f"Failed files: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    print(f"Downloading {len(PDF_FILES)} ARCP PDFs to {OUTPUT_DIR}/\n")
    download_pdfs()
