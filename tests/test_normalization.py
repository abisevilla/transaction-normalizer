import json
import sys
from decimal import Decimal
from pathlib import Path
import pytest
from transaction_normalizer.adapters import amount
from transaction_normalizer.services import load, process, export, ImportFailure, Cancelled

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def transaction():
    return {"id": "test", "amount": "100.50", "currency": "USD", "timestamp": "2025-03-10 14:22:00", "status": "completed"}


def test_reference(tmp_path):
    batch = load(ROOT / "examples/transactions.json")
    assert batch.metrics.valid == 3
    assert batch.metrics.invalid == 0
    assert batch.metrics.processed == 3
    assert batch.metrics.statuses == {"SUCCESS": 3, "FAILED": 0, "PENDING": 0}
    assert batch.metrics.currencies == {"USD": Decimal("201.00"), "EUR": Decimal("99.99")}
    assert [r.normalized.id for r in batch.records] == ["tx_001", "204", "A-77"]
    assert {r.normalized.to_dict()["timestamp"] for r in batch.records} == {"2025-03-10T14:22:00Z"}
    target = tmp_path / "out.json"
    export(target, batch.records)
    output = json.loads(target.read_text(), parse_float=Decimal)
    assert output[0]["amount"] == Decimal("100.50")
    assert set(output[0]) == {"id", "amount", "currency", "timestamp", "status", "source"}
    assert '"amount": "' not in target.read_text()


@pytest.mark.parametrize("value", [True, None, "", "NaN", "Infinity", Decimal("NaN"), Decimal("Infinity"), "1,00", "1.001"])
def test_bad_amounts(transaction, value):
    transaction["amount"] = value
    record = process([transaction]).records[0]
    assert not record.normalized
    assert any(e.field == "amount" for e in record.errors)


@pytest.mark.parametrize("value", ["0", "-2.30", "9999999999999999999999999999999999.99"])
def test_amount_precision(transaction, value):
    transaction["amount"] = value
    assert process([transaction]).records[0].normalized.amount == Decimal(value)


@pytest.mark.parametrize("field,value", [("id", True), ("id", " "), ("currency", "GBP"), ("status", "unknown"), ("timestamp", "2025-02-30 01:00:00")])
def test_validation(transaction, field, value):
    transaction[field] = value
    assert not process([transaction]).records[0].normalized


def test_normalization_and_statuses(transaction):
    transaction.update(id=12, currency=" usd ", status=" PROCESSING ")
    tx = process([transaction]).records[0].normalized
    assert (tx.id, tx.currency, tx.status.value) == ("12", "USD", "PENDING")
    transaction["status"] = "error"
    assert process([transaction]).metrics.statuses["FAILED"] == 1


def test_detection_and_errors(transaction):
    results = process([42, {}, {"amount": "1"}, {"id": "a", "ref": "b"}, {"id": "incomplete"}, transaction])
    assert results.metrics.valid == 1
    assert results.metrics.invalid == 5
    assert [r.errors[0].code for r in results.records[:4]] == ["INVALID_RECORD", "UNKNOWN_SOURCE", "UNKNOWN_SOURCE", "AMBIGUOUS_SOURCE"]
    assert results.records[4].source == "source_a"
    assert len(results.records[4].errors) == 4


def test_duplicates(transaction):
    batch = process([transaction, dict(transaction)])
    assert batch.metrics.valid == 2
    assert batch.metrics.currencies["USD"] == Decimal("201.00")
    assert all(any(w.code == "DUPLICATE_ID" for w in r.warnings) for r in batch.records)


def test_timezones(transaction):
    record = process([transaction], "America/El_Salvador").records[0]
    assert record.normalized.to_dict()["timestamp"] == "2025-03-10T20:22:00Z"
    assert record.warnings[0].code == "ASSUMED_TIMEZONE"
    transaction["timestamp"] = "2025-03-10T14:22:00+02:00"
    record = process([transaction]).records[0]
    assert record.normalized.to_dict()["timestamp"] == "2025-03-10T12:22:00Z"
    assert record.warnings == []


@pytest.mark.parametrize("date", ["2025-03-09 02:30:00", "2025-11-02 01:30:00"])
def test_dst_rejected(transaction, date):
    transaction["timestamp"] = date
    assert process([transaction], "America/New_York").metrics.invalid == 1


def test_source_b_minor_units():
    data = {"transaction_id": 204, "total": 10050, "currency_code": "usd", "created_at": "10/03/2025 14:22", "state": "OK"}
    tx = process([data]).records[0].normalized
    assert tx.amount == Decimal("100.50")
    assert tx.timestamp.month == 3 and tx.timestamp.day == 10
    for value in (True, "10050", Decimal("10050.0")):
        data["total"] = value
        assert process([data]).metrics.invalid == 1


def test_source_c_requires_zone():
    data = {"ref": "a", "amount": "€99,99", "date": "2025-03-10T14:22:00", "result": "success"}
    assert process([data]).metrics.invalid == 1
    data["date"] += "Z"
    assert process([data]).records[0].normalized.currency == "EUR"


@pytest.mark.parametrize("content", ["{}", "[", "null", "42"])
def test_import_errors(tmp_path, content):
    path = tmp_path / "input.json"
    path.write_text(content)
    with pytest.raises(ImportFailure):
        load(path)


def test_missing_file(tmp_path):
    with pytest.raises(ImportFailure):
        load(tmp_path / "missing")


def test_nonfinite_report(tmp_path):
    path = tmp_path / "input.json"
    path.write_text('[{"id":"a","amount":NaN}]')
    batch = load(path)
    out = tmp_path / "invalid.json"
    export(out, batch.records, invalid=True)
    data = json.loads(out.read_text())
    assert data[0]["original"]["amount"] == {"$nonfinite": "NaN"}
    assert data[0]["errors"]


def test_atomic_write_failure(tmp_path, monkeypatch, transaction):
    path = tmp_path / "out.json"
    path.write_text("previous")
    import transaction_normalizer.services as services
    def fail(*args):
        raise OSError("Disco no disponible")
    monkeypatch.setattr(services.os, "replace", fail)
    with pytest.raises(OSError):
        export(path, process([transaction]).records)
    assert path.read_text() == "previous"
    assert list(tmp_path.glob(".transactions-*")) == []


def test_progress_and_cancellation(transaction):
    notifications = []
    process([transaction] * 1000, progress=lambda a, b: notifications.append((a, b)))
    assert notifications[-1] == (1000, 1000)
    assert len(notifications) <= 101
    with pytest.raises(Cancelled):
        process([transaction], cancelled=lambda: True)


def test_empty_and_order():
    assert process([]).metrics.processed == 0
    data = json.loads((ROOT / "examples/transactions.json").read_text())
    assert [r.source for r in process(data[::-1]).records] == ["source_c", "source_b", "source_a"]


def test_decimal_json_reading(tmp_path, transaction):
    transaction["amount"] = 0
    path = tmp_path / "in.json"
    path.write_text(json.dumps([transaction]).replace('"amount": 0', '"amount": 0.29'))
    assert load(path).records[0].normalized.amount == Decimal("0.29")


def test_export_filters_and_invalid_report(tmp_path, transaction):
    batch = process([transaction, {"id": "bad"}, None])
    target = tmp_path / "filtered.json"
    export(target, batch.records[:1])
    assert len(json.loads(target.read_text())) == 1
    export(target, batch.records, invalid=True)
    report = json.loads(target.read_text())
    assert [r["index"] for r in report] == [1, 2]
    assert report[0]["source"] == "source_a"
    assert all({"code", "field", "message"} == set(e) for r in report for e in r["errors"])


def test_all_state_totals(transaction):
    records = [dict(transaction, status=state) for state in ("completed", "failed", "pending")]
    metrics = process(records).metrics
    assert metrics.currencies["USD"] == Decimal("301.50")
    assert metrics.statuses == {"SUCCESS": 1, "FAILED": 1, "PENDING": 1}


@pytest.mark.parametrize("missing", [None, "", "   ", "__absent__"])
def test_incomplete_category(transaction, missing):
    transaction["status"] = "unknown"  # Se conservan también errores independientes.
    if missing == "__absent__":
        transaction.pop("amount")
    else:
        transaction["amount"] = missing
    batch = process([transaction])
    record = batch.records[0]
    assert record.category == "INCOMPLETE"
    assert any(e.code == "MISSING_FIELD" and e.field == "amount" for e in record.errors)
    assert any(e.field == "status" for e in record.errors)
    assert (batch.metrics.valid, batch.metrics.invalid, batch.metrics.incomplete, batch.metrics.invalid_only) == (0, 1, 1, 0)


def test_initial_dataset_and_category_exports(tmp_path):
    path = ROOT / "src/transaction_normalizer/data/transactions_500.json"
    data = json.loads(path.read_text())
    assert len(data) == 500
    assert all(isinstance(row, dict) for row in data)
    batch = load(path)
    m = batch.metrics
    assert (m.processed, m.valid, m.invalid_only, m.incomplete) == (500, 300, 100, 100)
    assert m.valid + m.invalid == m.processed
    assert m.statuses == {"SUCCESS": 102, "FAILED": 99, "PENDING": 99}
    assert m.currencies == {"USD": Decimal("21413.00"), "EUR": Decimal("43031.50")}
    for category, count in (("VALID", 300), ("INVALID", 100), ("INCOMPLETE", 100)):
        records = [r for r in batch.records if r.category == category]
        target = tmp_path / f"{category}.json"
        export(target, records, invalid=category != "VALID")
        result = json.loads(target.read_text())
        assert len(result) == count
        if category != "VALID":
            assert all(r["category"] == category for r in result)
