from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel
from ..domain import Record

HEADERS = ("ID", "Monto", "Moneda", "Fecha (UTC)", "Estado", "Fuente", "Diagnóstico")


class TransactionModel(QAbstractTableModel):
    def __init__(self, records=None, parent=None):
        super().__init__(parent)
        self.records: list[Record] = records or []

    def replace(self, records):
        self.beginResetModel()
        self.records = records
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return HEADERS[section]
        return super().headerData(section, orientation, role)

    def value(self, row, column):
        record = self.records[row]
        tx = record.normalized
        if tx:
            return (tx.id, tx.amount, tx.currency, tx.timestamp, tx.status.value, tx.source,
                    "; ".join(i.message for i in record.warnings))[column]
        data = record.original if isinstance(record.original, dict) else {}
        raw_id = next((data[k] for k in ("id", "transaction_id", "ref") if k in data), "")
        return (str(raw_id), "", "", "", "", record.source or "Desconocida",
                "; ".join(i.message for i in record.errors))[column]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            value = self.value(index.row(), index.column())
            return value.isoformat().replace("+00:00", "Z") if hasattr(value, "isoformat") else str(value)
        return None


class TransactionProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_filter = self.status_filter = self.currency_filter = self.search = ""

    def refresh(self):
        # invalidate() remains compatible with the minimum supported Qt version.
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        values = [model.value(row, c) for c in range(6)]
        return (not self.source_filter or values[5] == self.source_filter) and (not self.status_filter or values[4] == self.status_filter) and (not self.currency_filter or values[2] == self.currency_filter) and self.search.casefold() in values[0].casefold()

    def lessThan(self, left, right):
        return self.sourceModel().value(left.row(), left.column()) < self.sourceModel().value(right.row(), right.column())
