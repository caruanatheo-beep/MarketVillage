import pytest


@pytest.fixture(autouse=True)
def skip_employer_pacing_for_offline_tests(request, monkeypatch):
    name = request.node.path.name
    if name.startswith("test_internships_") or name == "test_workday_pagination.py":
        if request.node.get_closest_marker("live") is None:
            from internships_project import internships

            monkeypatch.setattr(internships._RequestPacer, "wait", lambda self: None)
