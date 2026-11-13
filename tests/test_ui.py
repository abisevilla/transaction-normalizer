import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from time import monotonic
from decimal import Decimal
import pytest
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from transaction_normalizer.services import load, process
from transaction_normalizer.ui.models import TransactionModel, TransactionProxy
from transaction_normalizer.ui.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application
    import gc
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_numeric_sort_and_selection(app):
    data = [{"id": str(i), "amount": str(i), "currency": "USD", "timestamp": "2025-03-10 14:22:00", "status": "success"} for i in (100, 2, 10)]
    model = TransactionModel(process(data).records)
    proxy = TransactionProxy()
    proxy.setSourceModel(model)
    proxy.sort(1, Qt.AscendingOrder)
    assert [model.records[proxy.mapToSource(proxy.index(i, 0)).row()].normalized.amount for i in range(3)] == [Decimal(2), Decimal(10), Decimal(100)]
    proxy.search = "10"
    proxy.refresh()
    assert proxy.rowCount() == 2
    proxy.currency_filter = "EUR"
    proxy.refresh()
    assert proxy.rowCount() == 0


def test_window_filters_detail_and_metrics(app):
    window = MainWindow()
    batch = load(ROOT / "examples/transactions.json")
    window.display_batch(batch, "example.json", "UTC")
    window.show()
    app.processEvents()
    original_metrics = window.metrics_label.text()
    window.currency.setCurrentText("EUR")
    assert window.proxies[0].rowCount() == 1
    window.tables[0].selectRow(0)
    app.processEvents()
    assert "A-77" in window.original.toPlainText()
    assert "source_c" in window.normalized.toPlainText()
    assert window.metrics_label.text() == original_metrics
    window.tabs.setCurrentIndex(1)
    assert not window.currency.isEnabled()
    window.clear_filters()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_worker_large_batch_and_shutdown(app, tmp_path):
    import json
    data = json.loads((ROOT / "examples/transactions.json").read_text()) * 4000
    path = tmp_path / "large.json"
    path.write_text(json.dumps(data))
    window = MainWindow()
    window.import_path(path)
    ticks = 0
    deadline = monotonic() + 30
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
        ticks += 1
    assert window.worker is None
    assert window.batch.metrics.processed == 12000
    assert ticks > 1
    window.import_path(path)
    window.close()
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
    assert window.worker is None
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_worker_failure_preserves_batch(app, tmp_path, monkeypatch):
    window = MainWindow()
    batch = load(ROOT / "examples/transactions.json")
    window.display_batch(batch, "previous.json", "UTC")
    failures = []
    monkeypatch.setattr(window, "job_failed", failures.append)
    window.import_path(tmp_path / "missing.json")
    deadline = monotonic() + 5
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
    assert window.worker is None
    assert failures
    assert window.batch is batch
    assert "previous.json" in window.file_label.text()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_export_dialog_scope_and_confirmation(app, tmp_path, monkeypatch):
    import json
    from PySide6.QtWidgets import QInputDialog, QFileDialog, QMessageBox
    window = MainWindow()
    window.display_batch(load(ROOT / "examples/transactions.json"), "example.json", "UTC")
    window.currency.setCurrentText("EUR")
    target = tmp_path / "filtered.json"
    target.write_text("previous")
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Vista filtrada", True))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON"))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    window.choose_export(False)
    assert target.read_text() == "previous"
    assert window.worker is None
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    window.choose_export(False)
    deadline = monotonic() + 5
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
    assert window.worker is None
    output = json.loads(target.read_text())
    assert len(output) == 1 and output[0]["currency"] == "EUR"
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_automatic_initial_load_and_categories(app, tmp_path, monkeypatch):
    # La ruta de los datos no depende del directorio de ejecución.
    monkeypatch.chdir(tmp_path)
    window = MainWindow(autoload=True)
    deadline = monotonic() + 10
    while (window.batch is None or window.worker is not None) and monotonic() < deadline:
        app.processEvents()
    assert window.worker is None
    assert window.batch.metrics.processed == 500
    assert [model.rowCount() for model in window.models] == [300, 100, 100]
    assert "transactions_500.json" in window.file_label.text()
    assert "Incompletas: 100" in window.metrics_label.text()
    assert window.export_incomplete.isEnabled()
    window.tabs.setCurrentIndex(2)
    assert not window.state.isEnabled() and not window.currency.isEnabled()
    window.tables[2].selectRow(0)
    assert 'INCOMPLETE' in window.normalized.toPlainText()
    assert 'MISSING_FIELD' in window.normalized.toPlainText()
    window.source.setCurrentText("source_c")
    assert 0 < window.proxies[2].rowCount() < 100
    target = tmp_path / "incompletas.json"
    from PySide6.QtWidgets import QInputDialog, QFileDialog
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Lote completo", True))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON"))
    window.choose_export(True, incomplete=True)
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
    import json
    exported = json.loads(target.read_text())
    assert len(exported) == 100
    assert all(row['category'] == 'INCOMPLETE' for row in exported)
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
