from __future__ import annotations

from django import forms

from .models import Case, CaseContact, Deadline, FeedbackRequest, Note

# ---------------------------------------------------------------------------
# Shared widget CSS classes
# ---------------------------------------------------------------------------

_INPUT = (
    "block w-full rounded-card border border-cream-200 bg-white px-3 py-2.5 "
    "text-walnut-800 text-base placeholder-walnut-300 "
    "focus:border-terra-400 focus:ring-1 focus:ring-terra-400 focus:outline-none "
    "transition-colors duration-200"
)

_SELECT = _INPUT

_CHECKBOX = "h-4 w-4 rounded border-cream-200 text-terra-400 focus:ring-terra-400"

_TEXTAREA = (
    "block w-full rounded-card border border-cream-200 bg-white px-3 py-2.5 "
    "text-walnut-800 text-base placeholder-walnut-300 "
    "focus:border-terra-400 focus:ring-1 focus:ring-terra-400 focus:outline-none "
    "transition-colors duration-200 resize-y"
)


def _attrs(css: str, **extra: str) -> dict[str, str]:
    """Build a widget attrs dict with the given CSS classes."""
    return {"class": css, **extra}


# ---------------------------------------------------------------------------
# Case quick-add form
# ---------------------------------------------------------------------------


class QuickAddCaseForm(forms.ModelForm):
    """Minimal form for quickly creating a new case."""

    class Meta:
        model = Case
        fields = [
            "case_number",
            "caption",
            "short_name",
            "court",
            "county",
            "case_type",
            "jurisdiction",
            "plaintiff_name",
            "defendant_name",
        ]
        widgets = {
            "case_number": forms.TextInput(attrs=_attrs(_INPUT, placeholder="CV-2026-...")),
            "caption": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Smith v. Jones LLC")),
            "short_name": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Smith premises")),
            "court": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Jefferson County Circuit Court")),
            "county": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Jefferson")),
            "case_type": forms.Select(attrs=_attrs(_SELECT)),
            "jurisdiction": forms.Select(attrs=_attrs(_SELECT)),
            "plaintiff_name": forms.TextInput(attrs=_attrs(_INPUT)),
            "defendant_name": forms.TextInput(attrs=_attrs(_INPUT)),
        }


# ---------------------------------------------------------------------------
# Deadline quick-add form
# ---------------------------------------------------------------------------


class QuickAddDeadlineForm(forms.ModelForm):
    """Minimal form for quickly adding a deadline to a case."""

    class Meta:
        model = Deadline
        fields = [
            "case",
            "title",
            "due_date",
            "deadline_type",
            "is_extendable",
            "assigned_to",
        ]
        widgets = {
            "case": forms.Select(attrs=_attrs(_SELECT)),
            "title": forms.TextInput(attrs=_attrs(_INPUT, placeholder="File answer")),
            "due_date": forms.DateInput(attrs=_attrs(_INPUT, type="date")),
            "deadline_type": forms.Select(attrs=_attrs(_SELECT)),
            "is_extendable": forms.CheckboxInput(attrs=_attrs(_CHECKBOX)),
            "assigned_to": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Virginia")),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["case"].queryset = Case.objects.active().order_by("short_name")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Note inline form
# ---------------------------------------------------------------------------


class AddNoteForm(forms.ModelForm):
    """Inline form for adding a note to a case."""

    class Meta:
        model = Note
        fields = ["content", "note_type", "is_privileged"]
        widgets = {
            "content": forms.Textarea(attrs=_attrs(_TEXTAREA, rows="3", placeholder="Add a note...")),
            "note_type": forms.Select(attrs=_attrs(_SELECT)),
            "is_privileged": forms.CheckboxInput(attrs=_attrs(_CHECKBOX)),
        }


# ---------------------------------------------------------------------------
# Contact inline form
# ---------------------------------------------------------------------------


class AddContactForm(forms.ModelForm):
    """Inline form for adding a contact to a case."""

    class Meta:
        model = CaseContact
        fields = ["name", "role", "firm", "email", "phone"]
        widgets = {
            "name": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Name")),
            "role": forms.Select(attrs=_attrs(_SELECT)),
            "firm": forms.TextInput(attrs=_attrs(_INPUT, placeholder="Firm")),
            "email": forms.EmailInput(attrs=_attrs(_INPUT, placeholder="email@firm.com")),
            "phone": forms.TextInput(attrs=_attrs(_INPUT, placeholder="(205) 555-0100")),
        }


# ---------------------------------------------------------------------------
# Feedback form
# ---------------------------------------------------------------------------


class FeedbackRequestForm(forms.ModelForm):
    """Form for submitting a feedback request."""

    class Meta:
        model = FeedbackRequest
        fields = ["request_type", "title", "description", "priority"]
        widgets = {
            "request_type": forms.Select(attrs=_attrs(_SELECT)),
            "title": forms.TextInput(attrs=_attrs(_INPUT, placeholder="e.g., Add adjuster phone field")),
            "description": forms.Textarea(attrs=_attrs(
                _TEXTAREA,
                rows="4",
                placeholder="Describe what you need or what's not working...",
            )),
            "priority": forms.Select(attrs=_attrs(_SELECT)),
        }


# ---------------------------------------------------------------------------
# Deadline action forms
# ---------------------------------------------------------------------------


class CompleteDeadlineForm(forms.Form):
    """Form for marking a deadline complete with optional notes."""

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs=_attrs(_TEXTAREA, rows="2", placeholder="Completion notes (optional)")),
    )


class ExtendDeadlineForm(forms.Form):
    """Form for extending a deadline with a new due date and reason."""

    new_due_date = forms.DateField(
        widget=forms.DateInput(attrs=_attrs(_INPUT, type="date")),
    )
    reason = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs=_attrs(_INPUT, placeholder="Reason for extension")),
    )
