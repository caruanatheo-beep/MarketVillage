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


@pytest.mark.parametrize('title,location,expected', [
    ('Client Solutions Associate - San Francisco, CA', 'San Francisco, CA, USA', 'Client Solutions Associate'),
    ('Client Solutions Associate - Enterprise Data Solutions - San Francisco, CA | Boston, MA', 'San Francisco, CA, USA',
     'Client Solutions Associate - Enterprise Data Solutions | Boston, MA'),
    ('Equity Research MBA Analyst Summer Internship Programme - London, UK', 'London',
     'Equity Research MBA Analyst Summer Internship Programme'),
    ('Client Solutions Internship - Boston, Summer', 'United States, Boston, One Beacon Street', 'Client Solutions Internship - Summer'),
    ('MBA Summer Intern, Account Manager, APAC (Singapore, Hong Kong, Shanghai)', 'Singapore; Hong Kong; Shanghai, CHN',
     'MBA Summer Intern, Account Manager, APAC'),
    ('Analytics & Sales - London/South Africa Rotational Programme', 'London, United Kingdom',
     'Analytics & Sales - South Africa Rotational Programme'),
    ('Analytics & Sales Graduate Programme, Sydney - Asian Language Speakers', 'Sydney, Australia',
     'Analytics & Sales Graduate Programme - Asian Language Speakers'),
    ('Sales (Paris, FR)', 'Paris', 'Sales'),
    ('Client Solutions Associate - San Francisco, CA, February 2027', 'San Francisco, CA, USA', 'Client Solutions Associate'),
    ('Client Solutions Associate - Boston, MA, February 2027', 'United States, Boston, One Beacon Street',
     'Client Solutions Associate'),
    ('Client Solutions Associate - San Francisco, CA (February 2027)', 'San Francisco, CA, USA', 'Client Solutions Associate'),
    ('Client Solutions Associate – Los Angeles, CA – February 2027', 'United States, Los Angeles', 'Client Solutions Associate'),
    ('Sales/Trading - Rates', 'Paris', 'Sales/Trading - Rates'),
])
def test_removed_city_leaves_no_punctuation_or_code_residue(title, location, expected):
    result = jobs._display_offer_title(title, location)
    assert result == expected
    assert jobs._display_offer_title(result, location) == expected


@pytest.mark.parametrize('raw,expected', [
    ('Search', 'Non précisé'), ('Newport Beach, CA USA', 'Newport Beach · États-Unis'),
    ('Bogota  Colombia', 'Bogota · Colombie'), ('Le Relecq-Kerhuon (Près de Brest)', 'Le Relecq-Kerhuon · France'),
    ('Boulder, CO, USA', 'Boulder, CO · États-Unis'),
])
def test_listing_labels_and_additional_cities(raw, expected):
    assert jobs._display_offer_location(raw) == expected


def test_missing_location_falls_back_to_the_city_ending_the_title():
    title = 'Quantitative Masters Internship Program - Technology - Analytics & Modeling - San Francisco'
    assert jobs._display_offer_place('Search', title) == 'San Francisco · États-Unis'
    assert jobs._display_offer_place('Search', 'Sales Programme - Global Markets') == 'Non précisé'
    assert jobs._display_offer_place('Paris', title) == 'Paris · France'


@pytest.mark.parametrize('raw,expected', [
    ('6th September 2027', '6 septembre 2027'), ('1st of June 2027', '1er juin 2027'),
    ('September 6th, 2027', '6 septembre 2027'), ('21 June 2027', '21 juin 2027'), ('2027-04', 'avril 2027'),
])
def test_english_ordinal_start_dates_are_translated(raw, expected):
    assert jobs._display_offer_date(raw) == expected
