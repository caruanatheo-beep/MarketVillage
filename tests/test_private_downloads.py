from internships_project.private_downloads import (get_download, latest_download,
                                                   register_download, remove_user_downloads)


def test_pdf_download_is_bound_to_the_creating_account(tmp_path):
    pdf = tmp_path / "letter.pdf"
    pdf.write_bytes(b"%PDF-test")
    token = register_download("alice", str(pdf), ttl=3600)
    assert get_download(token, "alice") == pdf
    assert get_download(token, "bob") is None
    assert latest_download("alice") == pdf
    assert latest_download("bob") is None
    remove_user_downloads("alice")
