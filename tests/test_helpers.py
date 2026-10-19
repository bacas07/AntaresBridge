"""Unit puros AntaresBridge helpers: _parse_fechacita, _to_fechacita, _str_val, _str_int, _datetime_iso, _rows_to_dicts, _extract_time."""
import datetime
import decimal
from unittest.mock import MagicMock

from src.db.antares import (
    _parse_fechacita,
    _to_fechacita,
    _str_val,
    _str_int,
    _datetime_iso,
    _rows_to_dicts,
    _row_to_dict,
)
from src.sync.engine import serialize_row


def test_parse_fechacita_ok():
    assert _parse_fechacita("202610141140") == "2026-10-14T11:40:00"
    assert _parse_fechacita("202401011200") == "2024-01-01T12:00:00"


def test_parse_fechacita_bordes():
    assert _parse_fechacita(None) is None
    assert _parse_fechacita("") is None
    assert _parse_fechacita("20240101") is None
    assert _parse_fechacita("badstring12") is None
    assert _parse_fechacita("202402291200") == "2024-02-29T12:00:00"


def test_to_fechacita_datetime():
    dt = datetime.datetime(2026, 10, 14, 8, 0)
    assert _to_fechacita(dt) == "202610140800"


def test_to_fechacita_iso_str():
    assert _to_fechacita("2026-10-14T11:40:00") == "202610141140"
    assert _to_fechacita("2026-10-14T11:40:00+00:00") == "202610141140"


def test_str_val():
    assert _str_val(None, "x") == "x"
    assert _str_val("  hola ", "") == "hola"
    assert _str_val(123) == "123"


def test_str_int():
    assert _str_int("42", 0) == 42
    assert _str_int("bad", 7) == 7
    assert _str_int(None, 9) == 9


def test_datetime_iso():
    assert _datetime_iso(None) is None
    dt = datetime.datetime(2026, 10, 14, 11, 40)
    assert _datetime_iso(dt) == dt.isoformat()
    d = datetime.date(2026, 10, 14)
    assert _datetime_iso(d) == d.isoformat()
    assert _datetime_iso("  hola  ") == "hola"


def test_rows_to_dicts():
    cur = MagicMock()
    cur.description = [("id",), ("name",)]
    cur.fetchall.return_value = [(1, "a"), (2, "b")]
    assert _rows_to_dicts(cur) == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    cur2 = MagicMock()
    cur2.description = None
    assert _rows_to_dicts(cur2) == []


def test_row_to_dict():
    cur = MagicMock()
    cur.description = [("id",)]
    cur.fetchone.return_value = (99,)
    assert _row_to_dict(cur) == {"id": 99}
    cur.fetchone.return_value = None
    assert _row_to_dict(cur) is None


def test_extract_time_via_antares():
    from src.db.antares import _extract_time

    assert _extract_time("1899-12-30 08:00:00") == "08:00:00"
    assert _extract_time(None) is None
    assert _extract_time("0") is None


def test_serialize_row_tipos():
    dt = datetime.datetime(2026, 10, 14, 11, 40)
    d = datetime.date(2026, 10, 14)
    t = datetime.time(8, 0)
    row = {
        "a": dt,
        "b": d,
        "c": t,
        "d": decimal.Decimal("10.5"),
        "e": b"hola",
        "f": None,
        "g": "x",
    }
    out = serialize_row(row)
    assert out["a"] == dt.isoformat()
    assert out["b"] == d.isoformat()
    assert out["c"] == t.isoformat()
    assert out["d"] == 10.5
    assert out["e"] == "hola"
    assert out["f"] is None
    assert out["g"] == "x"
