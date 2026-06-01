import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    import db
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'test.db')

from db import init_db, get_progress, save_progress, save_available, get_all_available

def test_get_progress_default_zero():
    init_db()
    assert get_progress(3) == 0

def test_save_and_get_progress():
    init_db()
    save_progress(3, 1000)
    assert get_progress(3) == 1000

def test_save_progress_overwrites():
    init_db()
    save_progress(3, 1000)
    save_progress(3, 2000)
    assert get_progress(3) == 2000

def test_save_available_and_retrieve():
    init_db()
    save_available('abc.com')
    results = get_all_available()
    assert any(r['domain'] == 'abc.com' for r in results)

def test_save_available_ignores_duplicate():
    init_db()
    save_available('abc.com')
    save_available('abc.com')
    results = get_all_available()
    assert len([r for r in results if r['domain'] == 'abc.com']) == 1

def test_get_all_available_empty():
    init_db()
    assert get_all_available() == []
