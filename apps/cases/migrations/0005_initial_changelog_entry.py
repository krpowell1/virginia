from __future__ import annotations

from django.db import migrations


def create_initial_changelog(apps, schema_editor):
    """Create the welcome changelog entry."""
    ChangelogEntry = apps.get_model("cases", "ChangelogEntry")
    ChangelogEntry.objects.create(
        version="1.0.0",
        title="Welcome to Defense Case Manager",
        description=(
            "Your case tracker is live! You can add cases, track deadlines "
            "with automatic Alabama Rule 6 calculations, and see everything "
            "on your calendar. Face ID login is set up on your iPad. "
            "Tap the + button to add your first case."
        ),
    )


def remove_initial_changelog(apps, schema_editor):
    """Remove the welcome changelog entry."""
    ChangelogEntry = apps.get_model("cases", "ChangelogEntry")
    ChangelogEntry.objects.filter(version="1.0.0").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0004_changelog_models"),
    ]

    operations = [
        migrations.RunPython(create_initial_changelog, remove_initial_changelog),
    ]
