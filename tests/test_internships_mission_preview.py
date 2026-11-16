from datetime import datetime, timezone

import pytest

from internships_project import internships as m


@pytest.mark.parametrize("description", ["", "Missions : Analyser les spreads et les taux."])
def test_cards_omit_mission_preview_and_preserve_source_description(monkeypatch, description):
    monkeypatch.setattr(m, "source_checks", lambda: {})
    job = m.Opportunity("Stage Sales", "Bank", "Paris", "Stage",
                        "https://jobs.smartrecruiters.com/bank/1", "2026-11-09", 100,
                        description=description)
    board = m.render_opportunities([job], [], datetime.now(timezone.utc))
    card = board.split('<article ', 1)[1].split('</article>', 1)[0]
    assert 'class="job-mission-preview' not in card
    assert "Missions" not in card
    assert "Analyser les spreads" not in card
    assert card.index('class="job-title"') < card.index('class="job-key-facts"')
    assert card.count('<a ') == 1
    assert job.description == description
