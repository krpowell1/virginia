from __future__ import annotations

from django.urls import path

from . import views

app_name = "cases"

urlpatterns: list = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Case list
    path("cases/", views.case_list, name="list"),
    path("cases/partial/", views.case_list_partial, name="list-partial"),

    # Quick-add
    path("cases/add/", views.case_add, name="case-add"),
    path("deadlines/add/", views.deadline_add, name="deadline-add"),

    # Case detail + tabs
    path("cases/<str:pk>/", views.case_detail, name="detail"),
    path("cases/<str:pk>/tab/overview/", views.tab_overview, name="tab-overview"),
    path("cases/<str:pk>/tab/deadlines/", views.tab_deadlines, name="tab-deadlines"),
    path("cases/<str:pk>/tab/contacts/", views.tab_contacts, name="tab-contacts"),
    path("cases/<str:pk>/tab/notes/", views.tab_notes, name="tab-notes"),
    path("cases/<str:pk>/tab/activity/", views.tab_activity, name="tab-activity"),

    # Deadline actions
    path(
        "cases/<str:case_pk>/deadlines/<str:deadline_pk>/complete/",
        views.deadline_complete,
        name="deadline-complete",
    ),
    path(
        "cases/<str:case_pk>/deadlines/<str:deadline_pk>/extend/",
        views.deadline_extend,
        name="deadline-extend",
    ),

    # Note / Contact add
    path("cases/<str:pk>/notes/add/", views.note_add, name="note-add"),
    path("cases/<str:pk>/contacts/add/", views.contact_add, name="contact-add"),

    # Reports
    path("reports/", views.report_builder, name="reports"),
    path("reports/results/", views.report_results, name="report-results"),
    path("reports/export/", views.report_export, name="report-export"),

    # Search
    path("search/", views.global_search, name="search"),
    path("search/results/", views.search_results_partial, name="search-results"),

    # Feedback
    path("feedback/", views.feedback_list, name="feedback-list"),
    path("feedback/new/", views.feedback_create, name="feedback-create"),

    # Changelog
    path("changelog/", views.changelog, name="changelog"),
    path("changelog/dismiss/", views.changelog_dismiss, name="changelog-dismiss"),
]
