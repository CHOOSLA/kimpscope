import pytest
@pytest.fixture(autouse=True)
def no_external_model_in_unit_tests(monkeypatch):
    monkeypatch.setattr('backend.main.available',lambda:False)

@pytest.fixture(autouse=True)
def isolate_notice_database(tmp_path,monkeypatch):
    monkeypatch.setattr('backend.notices.DB',tmp_path/'notice-test.sqlite3')
