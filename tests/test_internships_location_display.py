"""Presentation must unify locations without merging actual places or changing source data."""
from dataclasses import replace

import pytest

from internships_project import internships as jobs


@pytest.mark.parametrize('raw',[
    'Paris','PARIS','Paris - France','Paris  - France','Paris, Île-de-France, France',
    'Paris, Ile-de-France, France','Paris, , France','Paris, Paris, France','PARIS (75)',
    'PARIS - 75','Paris, IDF, France','Paris, FR','Paris, 52 avenue Hoche','Paris, Origami',
    "PARIS\ue90f Domaine d'activité : Equities and Fixed Income\ue90f",
])
def test_paris_typography_regions_office_addresses_and_metadata_are_unified(raw):
    assert jobs._display_offer_location(raw)=='Paris · France'


@pytest.mark.parametrize('raw,expected',[
    ('Paris 8ème','Paris 8e · France'),('Paris 75015 - France','Paris 15e · France'),
    ('75001 Paris','Paris 1er · France'),('MONTROUGE','Montrouge · France'),
    ('Charenton le pont','Charenton-le-Pont · France'),('Paris - La Defense','La Défense · France'),
    ('Courbevoie (La Défense)','La Défense · France'),('Île de France','Île-de-France · France'),
    ('London, Greater London, England, United Kingdom','Londres · Royaume-Uni'),
    ('LONDON, LONDON, GBR','Londres · Royaume-Uni'),('Canary Wharf, 1 Churchill Place','Londres · Royaume-Uni'),
    ('Frankfurt am Main, Hessen, DE','Francfort · Allemagne'),('Frankfurt, Taunus Turm','Francfort · Allemagne'),
    ('Amsterdam, North Holland, Netherlands','Amsterdam · Pays-Bas'),('Switzerland - Zürich','Zurich · Suisse'),
    ('Geneva Place des Bergues 3','Genève · Suisse'),('Milano Via Turati 25-27','Milan · Italie'),
    ('Roma, Lazio, Italy','Rome · Italie'),('Lisbonne, Lisbonne, Portugal','Lisbonne · Portugal'),
    ('Luxembourg, Luxembourg, Luxembourg','Luxembourg'),('OCBC Singapore','Singapour'),
    ('SGP-Head Office','Singapour'),('Central, HKG','Hong Kong'),
    ('New York City, New York, United States of America','New York · États-Unis'),
    ('San Francisco, CA, United States','San Francisco · États-Unis'),('Boston, MA','Boston · États-Unis'),
    ('Seoul, KOR','Séoul · Corée du Sud'),('Shanghai, CHN','Shanghai · Chine'),
    ('Beijing, CHN','Pékin · Chine'),('Dubai, ARE','Dubaï · Émirats arabes unis'),
    ('Warsaw, Mazowieckie, Poland','Varsovie · Pologne'),('Wrocław','Wrocław · Pologne'),
    ('The Hague, Zuid-Holland, Netherlands','La Haye · Pays-Bas'),
    ('Sao Paulo Edificio Pedro Mariz','São Paulo · Brésil'),('Thailand','Thaïlande'),
    ('All','Non précisé'),('Madison Ave Corp','Non précisé'),('','Non précisé'),
])
def test_known_cities_countries_codes_and_districts(raw,expected):
    assert jobs._display_offer_location(raw)==expected
    assert jobs._display_offer_location(expected)==expected


@pytest.mark.parametrize('raw,expected',[
    ('London, Paris, Hong Kong, Tokyo','Londres · Royaume-Uni / Paris · France / Hong Kong / Tokyo · Japon'),
    ('New York, Seattle','New York · États-Unis / Seattle · États-Unis'),
    ('Paris / Montrouge','Paris · France / Montrouge · France'),
    ('Hong Kong, Singapore','Hong Kong / Singapour'),
    ('Paris, Texas, United States','Paris, Texas · États-Unis'),
    ('Singapore, United States','Singapore, United States'),
    ('Springfield, Illinois, United States','Springfield, Illinois · États-Unis'),
    ('Hong Kong Japan','Hong Kong Japan'),('Boston, IN, India','Boston · Inde'),
    ('Stafford','Stafford'),('Unknown City','Unknown City'),
])
def test_multiple_locations_and_conflicting_country_evidence_are_not_invented(raw,expected):
    assert jobs._display_offer_location(raw)==expected


def test_source_location_categories_and_deduplication_are_preserved():
    job=jobs.Opportunity('Sales Intern','Test','Paris, Ile-de-France, France','Stage',
                         'https://example.invalid/job','2026-11-11',100)
    assert jobs._display_offer_location(job.location)=='Paris · France'
    assert job.location=='Paris, Ile-de-France, France'
    assert jobs.matching_opportunities([job],category='Stages Paris')==[job]
    alternate=replace(job,location='Paris - France',url='https://example.invalid/other')
    assert len(jobs._deduplicate_opportunities([job,alternate]))==1
    assert jobs._is_international_location('Shanghai · Chine')
    assert not jobs._is_international_location('Montrouge · France')
