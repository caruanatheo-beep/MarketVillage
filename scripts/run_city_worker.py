"""Run MarketDesk City schedules once, independently of the web interface."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".venv" / "Lib" / "site-packages")]

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from internships_project.marketdesk_city import CityStore, CityWorker


def main() -> None:
    store = CityStore()
    store.recover_stale()
    store.enqueue_network_daily()
    store.enqueue_specialist_schedules()
    worker = CityWorker(store)
    while worker.run_once():
        pass
    store.enqueue_daily_digest()


if __name__ == "__main__":
    main()
