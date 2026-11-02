from types import SimpleNamespace

from src import ui


def test_research_download_paths_excludes_indexes_and_traversal(tmp_path, monkeypatch):
    root = tmp_path / "rag_documents"
    archive = root / "permanent"
    archive.mkdir(parents=True)
    pdf = root / "research.pdf"
    saved = archive / "saved.txt"
    pdf.write_bytes(b"%PDF-1.4")
    saved.write_text("published research", encoding="utf-8")
    (root / "rag_index.json").write_text("{}", encoding="utf-8")
    (archive / "manifest.json").write_text("[]", encoding="utf-8")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(ui, "RAG_ROOT", root)
    agent = SimpleNamespace(
        rag=SimpleNamespace(documents=lambda: [
            {"filename": "research.pdf"}, {"filename": "rag_index.json"},
            {"filename": "../outside.pdf"},
        ]),
        dynamic_rag=SimpleNamespace(archive=SimpleNamespace(
            root=archive,
            documents=lambda: [
                {"file": "saved.txt"}, {"file": "manifest.json"},
                {"file": "../../outside.pdf"},
            ],
        )),
    )

    assert ui.research_download_paths(agent) == sorted([str(pdf.resolve()), str(saved.resolve())])
