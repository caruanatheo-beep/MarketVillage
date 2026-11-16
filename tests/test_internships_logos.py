import base64
from io import BytesIO

from PIL import Image

from internships_project import internships as m
from scripts.fetch_company_logos import IconLinks, png_bytes


def test_new_company_names_resolve_to_bundled_valid_images():
    names = ['21shares', 'AXA', 'BPCE / Natixis / BRED', 'Business France', 'Comgest',
             'Crédit Agricole Titres', 'Da Vinci', 'Finance Active', 'Groupama AM', 'JobTeaser',
             'La Française', 'Natixis CIB London', 'Ofi Invest', 'Santander CIB', 'TD Securities',
             'WisdomTree', 'BBVA', 'Crédit Mutuel Arkéa', 'Jane Street', 'Optiver']
    for name in names:
        host = m.COMPANY_ICON_HOSTS[m._canonical_company(name)]
        with Image.open(m.COMPANY_LOGO_DIR / f'{host}.png') as logo:
            assert logo.format == 'PNG', name
            assert 0 < logo.width <= 96 and 0 < logo.height <= 96, name
            logo.verify()


def test_cached_logo_never_fetches_network_and_reuses_company_aliases(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "COMPANY_LOGO_DIR", tmp_path)
    image = Image.new("RGBA", (32, 32), "blue")
    image.save(tmp_path / "www.natixis.com.png")
    (tmp_path / "default.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    monkeypatch.setattr(m.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    m._local_company_icon.cache_clear()
    try:
        icon = m._company_icon("Natixis CIB Hong Kong")
        assert icon.startswith("data:image/png;base64,")
        assert icon == m._company_icon("Natixis CIB France")
        Image.open(BytesIO(base64.b64decode(icon.split(",", 1)[1]))).verify()
        assert m._company_icon("Unknown").startswith("data:image/svg+xml;base64,")
    finally:
        m._local_company_icon.cache_clear()


def test_downloaded_images_are_validated_and_bounded():
    source = BytesIO()
    Image.new("RGB", (500, 250), "red").save(source, "PNG")
    data = png_bytes(source.getvalue())
    with Image.open(BytesIO(data)) as image:
        assert image.size == (96, 48)
    import pytest
    with pytest.raises(OSError):
        png_bytes(b'<html>Access denied</html>')


def test_official_icon_links_are_discovered_from_page():
    parser = IconLinks()
    parser.feed('<link rel="stylesheet" href="style.css"><link rel="icon" href="/brand.png">'
                '<link rel="apple-touch-icon" href="/apple.png">')
    assert parser.urls == ["/brand.png", "/apple.png"]
