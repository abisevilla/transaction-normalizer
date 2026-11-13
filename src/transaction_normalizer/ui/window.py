"""Ventana principal y coordinación de trabajos en segundo plano."""
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import simplejson
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTabWidget, QTableView, QSplitter,
    QPlainTextEdit, QFileDialog, QMessageBox, QProgressBar, QAbstractItemView, QInputDialog)
from ..services import load, export, Cancelled, safe_original, metrics_for
from .models import TransactionModel, TransactionProxy, available_fields
from .theme import STYLE


class Worker(QThread):
    result = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            self.result.emit(self.action(self))
        except Cancelled:
            pass
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, autoload=False):
        super().__init__()
        self.setWindowTitle("Normalizador de transacciones")
        self.resize(1250, 820)
        self.setStyleSheet(STYLE)
        self.batch = None
        self.worker = None
        self.closing = False
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(QLabel("Explorador de transacciones", objectName="title"))
        actions = QHBoxLayout()
        self.open_button = QPushButton("Abrir JSON…")
        self.open_button.clicked.connect(self.choose_file)
        actions.addWidget(self.open_button)
        actions.addWidget(QLabel("Zona de origen (fechas sin zona):"))
        self.zone = QComboBox()
        self.zone.setEditable(True)
        self.zone.addItems(["UTC", "America/El_Salvador", "America/New_York", "Europe/Madrid"])
        self.zone.setAccessibleName("Zona de origen para la próxima importación")
        actions.addWidget(self.zone)
        actions.addStretch()
        self.export_valid = QPushButton("Exportar válidas…")
        self.export_invalid = QPushButton("Exportar inválidas…")
        self.export_valid.clicked.connect(lambda: self.choose_export(False))
        self.export_invalid.clicked.connect(lambda: self.choose_export(True))
        self.export_incomplete = QPushButton("Exportar incompletas…")
        self.export_incomplete.clicked.connect(lambda: self.choose_export(True, incomplete=True))
        layout.addLayout(actions)
        exports = QHBoxLayout()
        exports.addWidget(self.export_valid)
        exports.addWidget(self.export_invalid)
        exports.addWidget(self.export_incomplete)
        exports.addStretch()
        layout.addLayout(exports)
        self.file_label = QLabel("Abra un archivo JSON para comenzar. Los datos se procesan localmente.")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        self.metrics_label = QLabel("Sin lote cargado", objectName="metrics")
        self.metrics_label.setWordWrap(True)
        layout.addWidget(self.metrics_label)
        self.batch_label = QLabel("", objectName="batch_summary")
        self.batch_label.setWordWrap(True)
        layout.addWidget(self.batch_label)
        self.success_label = QLabel("", objectName="success")
        layout.addWidget(self.success_label)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar identificador…")
        self.search.setAccessibleName("Buscar por identificador")
        filters.addWidget(self.search)
        self.source = QComboBox()
        self.source.addItems(["Todas las fuentes", "source_a", "source_b", "source_c", "Desconocida"])
        self.state = QComboBox()
        self.state.addItems(["Todos los estados", "SUCCESS", "FAILED", "PENDING"])
        self.currency = QComboBox()
        self.currency.addItems(["Todas las monedas", "USD", "EUR"])
        for combo, name in ((self.source, "Fuente"), (self.state, "Estado"), (self.currency, "Moneda")):
            combo.setAccessibleName(name)
            filters.addWidget(combo)
            combo.currentIndexChanged.connect(self.apply_filters)
        self.search.textChanged.connect(self.apply_filters)
        clear = QPushButton("Limpiar filtros")
        clear.clicked.connect(self.clear_filters)
        filters.addWidget(clear)
        layout.addLayout(filters)
        splitter = QSplitter(Qt.Vertical)
        self.tabs = QTabWidget()
        self.models, self.proxies, self.tables = [], [], []
        for title in ("Válidas", "Inválidas", "Incompletas"):
            model = TransactionModel(parent=self)
            proxy = TransactionProxy(self)
            proxy.setSourceModel(model)
            table = QTableView()
            table.setModel(proxy)
            table.setSortingEnabled(True)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.horizontalHeader().setStretchLastSection(True)
            table.selectionModel().selectionChanged.connect(self.show_detail)
            self.models.append(model)
            self.proxies.append(proxy)
            self.tables.append(table)
            self.tabs.addTab(table, title)
        self.tabs.currentChanged.connect(self.apply_filters)
        splitter.addWidget(self.tabs)
        details = QWidget()
        detail_layout = QVBoxLayout(details)
        detail_layout.addWidget(QLabel("Detalle de la selección · original y normalizado"))
        comparison = QHBoxLayout()
        self.original = QPlainTextEdit()
        self.normalized = QPlainTextEdit()
        for editor, placeholder in ((self.original, "Datos originales"), (self.normalized, "Resultado, errores y advertencias")):
            editor.setReadOnly(True)
            editor.setPlaceholderText(placeholder)
            editor.setAccessibleName(placeholder)
            comparison.addWidget(editor)
        detail_layout.addLayout(comparison)
        splitter.addWidget(details)
        splitter.setSizes([370, 220])
        layout.addWidget(splitter)
        self.view_label = QLabel("Vista: 0 registros")
        layout.addWidget(self.view_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        open_action = QAction("Abrir JSON", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.choose_file)
        self.addAction(open_action)
        self.open_action = open_action
        self.set_busy(False)
        if autoload:
            QTimer.singleShot(0, self.load_default)

    def load_default(self):
        """Carga el archivo incluido en el paquete, sin depender del directorio actual."""
        path = Path(__file__).resolve().parents[1] / "data" / "transactions_500.json"
        self.import_path(path, "UTC")

    def set_busy(self, busy):
        self.open_button.setEnabled(not busy)
        self.open_action.setEnabled(not busy)
        self.zone.setEnabled(not busy)
        self.export_valid.setEnabled(not busy and self.batch is not None)
        self.export_invalid.setEnabled(not busy and self.batch is not None)
        self.export_incomplete.setEnabled(not busy and self.batch is not None)
        self.progress_bar.setVisible(busy)

    def start_job(self, action, completed):
        self.set_busy(True)
        self.progress_bar.setRange(0, 0)
        worker = Worker(action, self)
        self.worker = worker
        worker.result.connect(completed)
        worker.failed.connect(self.job_failed)
        worker.progress.connect(self.update_progress)
        worker.finished.connect(self.job_finished)
        worker.start()

    def update_progress(self, done, total):
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)

    def job_failed(self, message):
        if not self.closing:
            QMessageBox.warning(self, "No se completó la operación", message + "\nEl lote anterior se conserva si había uno cargado.")

    def job_finished(self):
        worker = self.worker
        self.worker = None
        self.set_busy(False)
        if worker:
            worker.deleteLater()
        if self.closing:
            QTimer.singleShot(0, self.close)

    def choose_file(self):
        if self.worker:
            return
        zone = self.zone.currentText().strip()
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):
            QMessageBox.warning(self, "Zona inválida", "Introduzca una zona IANA válida, por ejemplo UTC o America/El_Salvador.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir transacciones", "", "JSON (*.json);;Todos los archivos (*)")
        if path:
            self.import_path(path, zone)

    def import_path(self, path, zone="UTC"):
        if self.worker:
            return
        self.start_job(lambda w: load(path, zone, w.progress.emit, w.isInterruptionRequested),
                       lambda batch: self.display_batch(batch, path, zone))

    def display_batch(self, batch, path, zone):
        self.batch = batch
        self.models[0].replace([r for r in batch.records if r.normalized])
        self.models[1].replace([r for r in batch.records if r.category == "INVALID"])
        self.models[2].replace([r for r in batch.records if r.category == "INCOMPLETE"])
        for i, title in enumerate(("Válidas", "Inválidas", "Incompletas")):
            self.tabs.setTabText(i, f"{title} ({len(self.models[i].records)})")
        self.file_label.setText(f"Archivo: {Path(path).name} · Zona asumida: {zone}")
        m = batch.metrics
        self.batch_label.setText(f"Lote completo: {m.processed} registros · Válidas: {m.valid} · Inválidas: {m.invalid_only} · Incompletas: {m.incomplete}")
        self.clear_filters()
        self.original.clear()
        self.normalized.clear()
        for table in self.tables:
            table.resizeColumnsToContents()

    def apply_filters(self, *_):
        if self.batch is None:
            return
        source = self.source.currentText() if self.source.currentIndex() else ""
        # Las monedas disponibles dependen de la fuente, también en los rechazos.
        available = set()
        for record in self.batch.records:
            if not source or (record.source or "Desconocida") == source:
                available.add(available_fields(record)[0] or "Sin moneda")
        options = ["Todas las monedas"] + sorted(available)
        selected = self.currency.currentText()
        if options != [self.currency.itemText(i) for i in range(self.currency.count())]:
            self.currency.blockSignals(True)
            self.currency.clear()
            self.currency.addItems(options)
            self.currency.setCurrentText(selected if selected in options else "Todas las monedas")
            self.currency.blockSignals(False)
        for proxy in self.proxies:
            proxy.source_filter = source
            proxy.status_filter = self.state.currentText() if self.state.currentIndex() else ""
            proxy.currency_filter = self.currency.currentText() if self.currency.currentIndex() else ""
            proxy.search = self.search.text().strip()
            proxy.refresh()
        visible = []
        for i, title in enumerate(("Válidas", "Inválidas", "Incompletas")):
            proxy = self.proxies[i]
            self.tabs.setTabText(i, f"{title} ({proxy.rowCount()})")
            visible.extend(self.models[i].records[proxy.mapToSource(proxy.index(row, 0)).row()]
                           for row in range(proxy.rowCount()))
        m = metrics_for(visible)
        totals = " · ".join(f"{code} {value:,.2f}" for code, value in sorted(m.currencies.items())) or "Sin montos válidos"
        self.metrics_label.setText(f"VISTA FILTRADA   Registros: {m.processed}   |   Válidas: {m.valid}   |   Inválidas: {m.invalid_only}   |   Incompletas: {m.incomplete}\n"
                                   f"SUCCESS: {m.statuses['SUCCESS']}   FAILED: {m.statuses['FAILED']}   PENDING: {m.statuses['PENDING']}\n"
                                   f"Totales de válidas filtradas: {totals}")
        self.success_label.setText(f"{m.valid} transacciones válidas en la vista filtrada")
        self.view_label.setText(f"Pestaña actual: {self.proxies[self.tabs.currentIndex()].rowCount()} registros · Los conteos y montos superiores reflejan los filtros activos.")
        self.show_detail()

    def clear_filters(self):
        self.search.clear()
        for combo in (self.source, self.state, self.currency):
            combo.setCurrentIndex(0)
        self.apply_filters()

    def show_detail(self, *_):
        index = self.tabs.currentIndex()
        selected = self.tables[index].selectionModel().selectedRows()
        if not selected:
            self.original.clear()
            self.normalized.clear()
            return
        record = self.models[index].records[self.proxies[index].mapToSource(selected[0]).row()]
        self.original.setPlainText(simplejson.dumps(safe_original(record.original), ensure_ascii=False, indent=2, use_decimal=True))
        self.normalized.setPlainText(simplejson.dumps({"índice_original": record.index, "categoría": record.category,
            "normalizado": record.normalized.to_dict() if record.normalized else None,
            "errores": [vars(e) for e in record.errors], "advertencias": [vars(w) for w in record.warnings]},
            ensure_ascii=False, indent=2, use_decimal=True))

    def choose_export(self, invalid, incomplete=False):
        if not self.batch or self.worker:
            return
        scope, accepted = QInputDialog.getItem(
            self, "Alcance de exportación", "Registros a exportar:", ["Lote completo", "Vista filtrada"], 0, False)
        if not accepted:
            return
        index = 2 if incomplete else int(invalid)
        category_name = "incompletas" if incomplete else ("inválidas" if invalid else "válidas")
        if scope == "Vista filtrada":
            proxy = self.proxies[index]
            records = [self.models[index].records[proxy.mapToSource(proxy.index(row, 0)).row()] for row in range(proxy.rowCount())]
        else:
            records = list(self.models[index].records)
        path, _ = QFileDialog.getSaveFileName(self, f"Exportar {category_name} · {scope}", "incompletas.json" if incomplete else ("invalidas.json" if invalid else "normalizadas.json"), "JSON (*.json)")
        if not path:
            return
        if Path(path).exists() and QMessageBox.question(self, "Sobrescribir archivo", f"¿Reemplazar {Path(path).name}?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.start_job(lambda w: export(path, records, invalid, w.isInterruptionRequested),
                       lambda _: self.statusBar().showMessage(f"Exportación completada: {path} · {scope}", 10000))

    def closeEvent(self, event):
        if self.worker:
            self.closing = True
            self.worker.requestInterruption()
            self.statusBar().showMessage("Terminando la operación antes de cerrar…")
            event.ignore()
        else:
            event.accept()
