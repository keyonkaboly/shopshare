import importlib
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def test_secret_key_falls_back_to_dev_value(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import dotenv
    import infrastructure.security.hashing as hashing

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    reloaded = importlib.reload(hashing)

    assert reloaded.SECRET_KEY == "dev-secret-key"
