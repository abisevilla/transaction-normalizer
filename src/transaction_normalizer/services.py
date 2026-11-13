"""Importación y exportación atómica, sin dependencias gráficas."""
import json
import os
import tempfile
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo
import simplejson
from .adapters import ADAPTERS
from .domain import Batch, Issue, Metrics, Record


class ImportFailure(ValueError):
    """El archivo no pudo convertirse en un lote."""


class Cancelled(Exception):
    pass


def process(data: list, zone: str = "UTC", progress: Callable = lambda *_: None,
            cancelled: Callable = lambda: False) -> Batch:
    ZoneInfo(zone)
    if not isinstance(data, list):
        raise ImportFailure("La raíz del JSON debe ser una lista.")
    records = []
    duplicates = defaultdict(list)
    step = max(1, len(data) // 100)
    for index, original in enumerate(data):
        if cancelled():
            raise Cancelled()
        record = Record(index, original)
        if not isinstance(original, dict):
            record.errors.append(Issue("INVALID_RECORD", "", "La transacción debe ser un objeto."))
        else:
            matches = [a for a in ADAPTERS if a.matches(original)]
            if len(matches) != 1:
                code = "UNKNOWN_SOURCE" if not matches else "AMBIGUOUS_SOURCE"
                record.errors.append(Issue(code, "source", "Fuente desconocida." if not matches else "Coinciden varias fuentes."))
            else:
                record.source = matches[0].name
                matches[0].normalize(record, zone)
        if record.normalized:
            tx = record.normalized
            duplicates[(tx.source, tx.id)].append(record)
        records.append(record)
        if (index + 1) % step == 0 or index + 1 == len(data):
            progress(index + 1, len(data))
    for group in duplicates.values():
        if len(group) > 1:
            for record in group:
                record.warnings.append(Issue("DUPLICATE_ID", "id", "Identificador repetido en la misma fuente; se conservó el registro."))
    return Batch(records, metrics_for(records))


def metrics_for(records: Iterable[Record]) -> Metrics:
    """Resume un lote o una selección sin volver a normalizar sus registros."""
    metrics = Metrics()
    for record in records:
        metrics.processed += 1
        tx = record.normalized
        if tx is None:
            metrics.invalid += 1
            metrics.incomplete += record.category == "INCOMPLETE"
            continue
        metrics.valid += 1
        metrics.statuses[tx.status.value] += 1
        with localcontext() as ctx:
            previous = metrics.currencies.get(tx.currency, Decimal(0))
            ctx.prec = max(28, len(previous.as_tuple().digits), len(tx.amount.as_tuple().digits)) + 2
            metrics.currencies[tx.currency] = previous + tx.amount
    return metrics


def load(path: str | Path, zone="UTC", progress=lambda *_: None, cancelled=lambda: False) -> Batch:
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream, parse_float=Decimal, parse_constant=Decimal)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ImportFailure(f"No se pudo leer el JSON: {exc}") from exc
    return process(data, zone, progress, cancelled)


def safe_original(value: Any) -> Any:
    """Valores no finitos se representan como objetos etiquetados en reportes."""
    if isinstance(value, Decimal) and not value.is_finite():
        return {"$nonfinite": str(value)}
    if isinstance(value, dict):
        return {key: safe_original(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_original(item) for item in value]
    return value


def export(path: str | Path, records: Iterable[Record], invalid: bool = False, cancelled: Callable = lambda: False) -> None:
    path = Path(path)
    payload = []
    for record in records:
        if cancelled():
            raise Cancelled()
        if invalid and record.normalized is None:
            payload.append({"index": record.index, "original": safe_original(record.original),
                            "source": record.source, "category": record.category, "errors": [asdict(e) for e in record.errors]})
        elif not invalid and record.normalized:
            payload.append(record.normalized.to_dict())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".transactions-", suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            simplejson.dump(payload, stream, ensure_ascii=False, indent=2, use_decimal=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        if cancelled():
            raise Cancelled()
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
