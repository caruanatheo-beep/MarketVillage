"""Local City launcher waits for ongoing work before activating a new commit."""
from internships_project import state_store
from internships_project.marketdesk_city import CityStore
from scripts import city_start


def test_launcher_waits_for_running_missions(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'city.db')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', 'job_hunter', 'Examine le code', {'operation': 'repository_audit'})
    assert city_start.missions_running() is False
    store.claim_next()
    assert city_start.missions_running() is True
    store.finish(task['id'], result={'title': 'Examen terminé'})
    assert city_start.missions_running() is False
