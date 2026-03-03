from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def register_passkey(request: object) -> object:
    """Prompt the authenticated user to register a passkey (Face ID).

    After initial password login, the user is redirected here to enroll
    their device biometric so future logins use Face ID instead.
    """
    return render(request, "accounts/register_passkey.html")
