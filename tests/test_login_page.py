from fastapi.testclient import TestClient
from gradio.routes import App

from internships_project.internships_ui import build_internships_app
from internships_project.login_page import auth_message


def test_login_design_uses_gradio_auth_and_protects_config():
    demo = build_internships_app()
    demo.auth = [("preview", "preview-password-123")]
    demo.auth_message = auth_message()
    client = TestClient(App.create_app(demo))

    anonymous = client.get("/")
    assert anonymous.status_code == 200
    assert "Bienvenue" in anonymous.text
    assert "career-auth-content" in anonymous.text
    assert client.get("/config").status_code == 401
    assert client.post("/login", data={"username": "preview", "password": "wrong"}).status_code == 400
    assert client.post("/login", data={"username": "preview", "password": "preview-password-123"}).status_code == 200
    assert client.get("/config").status_code == 200
