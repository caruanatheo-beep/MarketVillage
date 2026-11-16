"""Resume the authorized, bounded Sacha source campaign."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.venv/Lib/site-packages')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from internships_project.city_source_campaign import main
main()
