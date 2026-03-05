# Alabama Rules of Civil Procedure — Extracted Text

Operative rule text extracted from official PDFs published by the
Alabama Judicial System at `judicial.alabama.gov/docs/library/rules/`.

## What's Included

- **41 rules** (Rules 3–68) covering civil procedure
- Only **current operative text** — committee comments, amendment history,
  and reporter notes have been stripped
- District court `(dc)` provisions are preserved
- Amendment history lines (`[Amended eff. ...]`) are excluded

## Directory Structure

```
data/arcp/
├── pdfs/              # Original PDFs from judicial.alabama.gov
│   ├── cv3.pdf
│   ├── cv4.pdf
│   └── ...
├── text/              # Cleaned text files (one per rule)
│   ├── rule_3.txt
│   ├── rule_4.txt
│   └── ...
├── arcp_combined.txt  # All rules in one file
└── README.md          # This file
```

## Scripts

- `scripts/download_arcp.py` — Downloads PDFs (skips existing files)
- `scripts/extract_arcp.py` — Extracts and cleans rule text using pdfplumber

## Rules Covered

| Rule | Title |
|------|-------|
| 3 | Commencement of action |
| 4 | Process: General and miscellaneous provisions |
| 5 | Service and filing of pleadings and other papers |
| 6 | Time |
| 7 | Pleadings allowed; form of motions |
| 8 | General rules of pleading |
| 9 | Pleading special matters |
| 10 | Form of pleadings |
| 11 | Signing of pleadings, motions, or other papers |
| 12 | Defenses and objections |
| 13 | Counterclaim and cross-claim |
| 14 | Third-party practice |
| 15 | Amended and supplemental pleadings |
| 16 | Pre-trial conferences; scheduling; management |
| 17 | Parties plaintiff and defendant; capacity |
| 18 | Joinder of claims and remedies |
| 19 | Joinder of persons needed for just adjudication |
| 20 | Permissive joinder of parties |
| 21 | Misjoinder and nonjoinder of parties |
| 22 | Interpleader |
| 23 | Class actions |
| 24 | Intervention |
| 25 | Substitution of parties |
| 26 | General provisions governing discovery |
| 27 | Discovery before action or pending appeal |
| 30 | Depositions upon oral examination |
| 33 | Interrogatories to parties |
| 34 | Production of documents and things |
| 36 | Requests for admission |
| 37 | Failure to make discovery: Sanctions |
| 38 | Jury trial of right |
| 41 | Dismissal of actions |
| 45 | Subpoena |
| 47 | Jurors |
| 50 | Judgment as a matter of law |
| 51 | Instructions to jury: Objection |
| 52 | Findings by the court; judgment on partial findings |
| 55 | Default |
| 56 | Summary judgment |
| 59 | New trials; amendment of judgments |
| 68 | Offer of judgment |

## Note

Rule 7A (cv7A.pdf) was listed in the original download set but returns
a 404 from judicial.alabama.gov as of March 2026.

## Source

Alabama Judicial System: https://judicial.alabama.gov/library/rules/civil-procedure
