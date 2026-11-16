from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from internships_project import internships as m
from internships_project import internships_ui as ui


@pytest.fixture
def view(monkeypatch):
    monkeypatch.setattr(ui, 'shared_mode', lambda: False)
    monkeypatch.setattr(ui, 'local_state_enabled', lambda: False)
    monkeypatch.setattr(ui, 'load_candidate_profile', lambda: '')
    monkeypatch.setattr(ui, 'hydrate_local_state', lambda *a: ({}, {}))
    job = m.Opportunity('Rates Sales Intern', 'Bank', 'Paris', 'Stage',
                        'https://example.invalid/sales', '2026-11-09', 90)
    jobs = [job]
    updated = datetime(2026, 11, 10, tzinfo=timezone.utc)
    load = Mock(side_effect=lambda **kw: (jobs, [], updated))
    render = Mock(return_value='cards')
    checks = {}
    monkeypatch.setattr(ui, 'load_opportunities', load)
    monkeypatch.setattr(ui, 'opportunities_loading', lambda: False)
    monkeypatch.setattr(ui, 'source_checks', lambda: checks)
    monkeypatch.setattr(ui, 'render_opportunities', render)
    monkeypatch.setattr(ui, 'render_tracking', Mock(return_value='tracking'))
    app = ui.build_internships_app()
    funcs = {fn.fn.__name__: fn.fn for fn in app.fns.values() if fn.fn}
    inputs = ['Toutes', '', 'Tous métiers', 'Toutes dates', {}, {}, True, 'all', 'pertinence']
    yield funcs, inputs, jobs, checks, load, render
    app.close()


def test_idle_timer_skips_render_and_leaves_every_component_untouched(view):
    funcs, inputs, jobs, checks, load, render = view
    initial = funcs['show_internships'](*inputs)
    render.reset_mock()
    load.reset_mock()
    match = Mock(side_effect=AssertionError('unchanged data must not be filtered again'))
    original = ui.matching_opportunities
    ui.matching_opportunities = match
    try:
        result = funcs['refresh_internship_timer'](*inputs, None, initial[3], None)
    finally:
        ui.matching_opportunities = original
    assert len(result) == len(initial)
    assert all(item == ui.gr.skip() for item in result)
    render.assert_not_called()
    load.assert_called_once()


@pytest.mark.parametrize('change', ['content', 'filters', 'status', 'loading', 'tracking'])
def test_timer_updates_real_changes_with_same_timestamp(view, monkeypatch, change):
    funcs, inputs, jobs, checks, load, render = view
    initial = funcs['show_internships'](*inputs)
    render.reset_mock()
    if change == 'content': jobs[0] = replace(jobs[0], location='Londres')
    if change == 'filters': inputs[1] = 'Sales'
    if change == 'status': checks['BBVA'] = {'status':'empty'}
    if change == 'loading': monkeypatch.setattr(ui, 'opportunities_loading', lambda: True)
    if change == 'tracking': inputs[4] = {jobs[0].url: {'status':'Postulé'}}
    result = funcs['refresh_internship_timer'](*inputs, jobs[0].url, initial[3], None)
    render.assert_called_once()
    assert result[0] == 'cards'
    assert result[1].value == jobs[0].url
    assert result[3]['view_key'] != initial[3]['view_key']


@pytest.mark.parametrize('raw,display', [
    ('2027-04-06','6 avril 2027'), ('06/04/2027','6 avril 2027'),
    ('2027-04','avril 2027'), ('January 2027','janvier 2027'),
    ('June 21, 2027','21 juin 2027'), ('21 June 2027','21 juin 2027'),
    ('March/April 2027','mars/avril 2027'), ('Dès que possible','Dès que possible'),
    ('2027-13','2027-13'), ('','Non précisé'),
])
def test_display_dates_preserve_precision_and_ranges(raw, display):
    assert m._display_offer_date(raw) == display
