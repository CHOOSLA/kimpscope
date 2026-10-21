import pytest
@pytest.fixture(autouse=True)
def no_external_model_in_unit_tests(monkeypatch):
    monkeypatch.setattr('backend.main.available',lambda:False)
