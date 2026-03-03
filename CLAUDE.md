# Defense Case Manager

## What This Is

A privacy-first legal case management system for an Alabama defense litigation attorney.
Django + HTMX web app deployed on a Hetzner VPS, accessed via iPad Safari as a PWA
with Face ID login. Tracks cases, auto-calculates deadlines using Alabama Rules of Civil
Procedure, syncs to Apple Calendar.

## Who This Is For

Virginia Powell, associate defense attorney at Starnes Davis Florie (Birmingham, AL).
Premises liability focus. Works under supervising partner Warren. Coordinates with
paralegal Mary. Currently tracks all cases, deadlines, and tasks mentally. This system
replaces that.

## Tech Stack (locked, do not change)

- Python 3.12+ (specify in all configs)
- Django 5.1.x (LTS track)
- HTMX 2.0 (no React, no Vue, no separate JS framework)
- Alpine.js 3.x (minimal client-side interactivity only)
- Tailwind CSS 4.x (via CDN for Phase 1, build step later)
- SQLite 3.x with WAL mode and FTS5
- Litestream 0.5.x for S3 backup replication
- Gunicorn as WSGI server
- Caddy 2 as reverse proxy (auto TLS)
- Docker Compose for deployment
- django-htmx, django-ical, django-otp-webauthn, workalendar

## Project Structure

defense-case-manager/
├── CLAUDE.md                    # This file
├── docker-compose.yml
├── Dockerfile
├── Caddyfile
├── litestream.yml
├── entrypoint.sh
├── requirements.txt
├── manage.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── __init__.py
│   ├── cases/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── managers.py
│   │   ├── admin.py
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── urls.py
│   │   ├── feeds.py              # django-ical webcal feed
│   │   ├── deadlines.py          # ARCP Rule 6 calculator
│   │   ├── alabama_calendar.py
│   │   ├── signals.py
│   │   ├── apps.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_deadlines.py
│   │   │   ├── test_models.py
│   │   │   └── test_views.py
│   │   └── templates/
│   │       └── cases/
│   │           ├── base.html
│   │           ├── dashboard.html
│   │           ├── case_list.html
│   │           ├── case_detail.html
│   │           └── partials/
│   │               ├── deadline_list.html
│   │               ├── deadline_row.html
│   │               ├── case_row.html
│   │               └── note_form.html
│   └── accounts/
│       ├── __init__.py
│       ├── views.py
│       ├── urls.py
│       ├── apps.py
│       └── templates/
│           └── accounts/
│               └── login.html
├── static/
│   ├── css/
│   ├── js/
│   │   ├── htmx.min.js
│   │   └── alpine.min.js
│   ├── icons/
│   ├── manifest.json
│   └── service-worker.js
├── templates/
│   └── base.html                # Global base template
└── staticfiles/                 # collectstatic output

## Coding Standards

- `from __future__ import annotations` at the top of EVERY Python file
- Type hints on all function signatures
- Docstrings on all classes and non-trivial functions
- Django model fields must have `help_text` for anything non-obvious
- No system-level dependencies (pure Python only)
- Use UUID primary keys on all models (not auto-incrementing integers)
- All model mutations must create an ActivityLog entry
- Tests use pytest-django, not unittest
- Template naming: `app_name/template_name.html`
- HTMX partials go in `templates/cases/partials/`
- CSRF token via meta tag + hx-headers on body, not per-form

## Alabama-Specific Rules (Critical)

The deadline calculator in `deadlines.py` implements ARCP Rule 6:

- Periods < 11 days: exclude weekends and Alabama holidays (business days only)
- Periods >= 11 days: count all calendar days
- If deadline lands on weekend/holiday: roll to next business day
- Rule 6(e): +3 days for mail or e-file service
- Day 1 is the day AFTER the trigger event

Non-extendable deadlines (NEVER allow extension via UI):

- Rule 50(b): Renewed JML (30 days from judgment)
- Rule 52(b): Amended findings (30 days)
- Rule 59(b): New trial motion (30 days)
- Rule 59(e): Alter/amend judgment (30 days)
- Rule 59.1: Auto-denial (90 days from motion filing)
- ARAP 4(a)(1): Notice of appeal (42 days, jurisdictional)
- 28 U.S.C. 1446: Federal removal (30 days, jurisdictional)

Alabama is pure contributory negligence (1 of ~5 states). Must be pled in Answer or
permanently waived. The Case model has a `pled_contributory_negligence` boolean that
the UI should prominently flag when False.

Mardi Gras is a court holiday ONLY in Mobile and Baldwin counties. The calendar must be
county-aware.

## Build Sequence (follow this order)

### Phase 1a: Models + Admin + Calendar (Weekend 1, Saturday)

1. Django project scaffold with settings (SQLite WAL, timezone, static files)
2. All models: Case, Deadline, CaseContact, Note, ActivityLog + managers
3. Alabama court calendar (workalendar subclass with Juneteenth, Mardi Gras)
4. Deadline calculator with all Rule 6 logic
5. Django admin with inlines, filters, search, and deadline urgency display
6. Signals: auto-generate deadlines when date_served is set
7. Webcal feed via django-ical
8. Tests: all 14 deadline calculation test cases must pass

### Phase 1b: Deploy + Verify (Weekend 1, Sunday)

1. Dockerfile + entrypoint.sh (handles migration before Gunicorn)
2. docker-compose.yml (web + litestream + caddy)
3. Caddyfile with security headers
4. litestream.yml for S3 replication
5. Deploy to Hetzner, create superuser, verify from iPad

### Phase 2: HTMX Frontend (Weekend 2)

1. Base template with Tailwind, HTMX, Alpine.js
2. Dashboard view (overdue, today, this week, attention needed)
3. Case list with HTMX search/filter
4. Case detail with tabbed layout (overview, deadlines, contacts, notes, activity)
5. Quick-add forms for cases and deadlines
6. WebAuthn/Face ID authentication
7. PWA manifest + service worker

## Key Design Decisions

- Deadline status (overdue/pending) is computed via `@property`, NOT stored in DB. No cron job needed.
- Contact model is case-scoped in Phase 1 (same person = separate records per case). Refactor to M2M in Phase 2.
- Notes are separate from Case.notes field to support chronological history with attribution.
- ActivityLog is immutable. No edit, no delete permissions in admin.
- The webcal feed is the primary notification channel in Phase 1 (Apple Calendar handles alerts).
- Face ID via WebAuthn is Phase 2. Phase 1 uses Django session auth via admin login.

## Environment Variables

DJANGO_SECRET_KEY=<generate 50 char random>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=portal.smithdefense.com
WEBAUTHN_RP_ID=portal.smithdefense.com
WEBAUTHN_ORIGIN=https://portal.smithdefense.com
AWS_ACCESS_KEY_ID=<for litestream S3>
AWS_SECRET_ACCESS_KEY=<for litestream S3>
LITESTREAM_S3_BUCKET=<bucket name>
DOMAIN=portal.smithdefense.com

## Testing

Run tests with: `python -m pytest apps/ -v`

The deadline tests are the most critical. All 14 must pass before any deployment. Test file:
`apps/cases/tests/test_deadlines.py`

Key test scenarios:

1. Answer deadline (personal service, weekday)
2. Answer deadline (mail service, +3 days, weekend roll)
3. Answer deadline landing on Memorial Day
4. Answer deadline landing on Confederate Memorial Day
5. Mardi Gras in Baldwin County (holiday)
6. Mardi Gras NOT in Jefferson County (not a holiday)
7. Short period (<11 days) business day counting
8. Short period spanning holiday
9. RFA response (standard 30 days)
10. RFA response (early discovery 45 days)
11. Post-judgment motion (non-extendable)
12. Rule 59.1 auto-denial (90 days)
13. Appeal from auto-denial (42 days, jurisdictional)
14. Service generates multiple deadlines (answer + removal + internal)

## Common Patterns

### HTMX partial response
```python
def deadline_list(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    deadlines = case.deadlines.filter(status='PENDING').order_by('due_date')
    return render(request, 'cases/partials/deadline_list.html', {
        'deadlines': deadlines
    })
```

### ActivityLog on every mutation
```python
def complete_deadline(request, deadline_id):
    deadline = get_object_or_404(Deadline, pk=deadline_id)
    deadline.mark_complete(request.user, notes=request.POST.get('notes', ''))
    ActivityLog.objects.create(
        case=deadline.case,
        user=request.user,
        action='DEADLINE_COMPLETED',
        description=f"Completed: {deadline.title}"
    )
    # Return HTMX partial or redirect
```

### CSRF with HTMX (in base template)
```html
<meta name="csrf-token" content="{{ csrf_token }}">
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

## What NOT To Do

- Do NOT use React, Vue, or any SPA framework
- Do NOT use PostgreSQL (SQLite is correct for 1-3 users)
- Do NOT store deadline overdue status in the database
- Do NOT allow deletion of ActivityLog records
- Do NOT allow extension of non-extendable deadlines
- Do NOT use unicode bullet characters in templates (use proper HTML lists)
- Do NOT hardcode holidays (use workalendar + custom subclass)
- Do NOT skip the `from __future__ import annotations` import
- Do NOT use `WidthType.PERCENTAGE` in any docx generation
ENDOFFILE
