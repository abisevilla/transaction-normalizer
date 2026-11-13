"""Firmas de fuentes y conversiones explícitas."""
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from zoneinfo import ZoneInfo
from .domain import Issue, Record, Status, Transaction

CURRENCIES = {"USD": 2, "EUR": 2}
STATES = {"completed": Status.SUCCESS, "ok": Status.SUCCESS, "success": Status.SUCCESS,
          "failed": Status.FAILED, "error": Status.FAILED,
          "pending": Status.PENDING, "processing": Status.PENDING}


def identifier(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError("Se requiere un identificador textual o entero no vacío.")
    return str(value).strip()


def currency(value: object) -> str:
    if not isinstance(value, str) or value.strip().upper() not in CURRENCIES:
        raise ValueError("Moneda no admitida; use USD o EUR.")
    return value.strip().upper()


def amount(value: object, code: str, minor: bool = False, euro: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Monto numérico inválido.")
    if minor and not isinstance(value, int):
        raise ValueError("El monto debe ser un entero de unidades menores.")
    text = str(value).strip()
    if euro:
        if not re.fullmatch(r"€[+-]?\d+(?:,\d+)?", text):
            raise ValueError("Se espera un monto como €99,99.")
        text = text[1:].replace(",", ".")
    elif isinstance(value, str) and not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        raise ValueError("Use punto decimal sin separadores de miles.")
    try:
        number = Decimal(text)
        if not number.is_finite():
            raise ValueError("El monto debe ser finito.")
        with localcontext() as ctx:
            ctx.prec = max(28, len(number.as_tuple().digits) + abs(number.as_tuple().exponent) + 4)
            if minor:
                number /= Decimal(10) ** CURRENCIES[code]
            unit = Decimal(1).scaleb(-CURRENCIES[code])
            rounded = number.quantize(unit)
            if number != rounded:
                raise ValueError("Precisión superior a la permitida por la moneda.")
            return rounded
    except InvalidOperation as exc:
        raise ValueError("Monto inválido.") from exc


def date(value: object, source: str, zone: str) -> tuple[datetime, bool]:
    if not isinstance(value, str):
        raise ValueError("Fecha ausente o inválida.")
    text = value.strip()
    try:
        if source == "source_b":
            if not re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", text):
                raise ValueError()
            parsed = datetime.strptime(text, "%d/%m/%Y %H:%M")
        else:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", text):
                raise ValueError()
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Fecha inválida para el formato de la fuente.") from exc
    assumed = parsed.tzinfo is None
    if assumed:
        if source == "source_c":
            raise ValueError("La fecha de source_c requiere zona horaria.")
        tz = ZoneInfo(zone)
        candidates = set()
        for fold in (0, 1):
            candidate = parsed.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
            if candidate.astimezone(tz).replace(tzinfo=None) == parsed:
                candidates.add(candidate)
        if len(candidates) != 1:
            raise ValueError("Hora local ambigua o inexistente por cambio de horario.")
        parsed = candidates.pop()
    return parsed.astimezone(timezone.utc), assumed


@dataclass(frozen=True)
class Adapter:
    name: str
    distinctive: frozenset[str]
    fields: tuple[str, str, str | None, str, str]
    states: dict[str, Status]

    def matches(self, data: dict) -> bool:
        return bool(self.distinctive.intersection(data))

    def normalize(self, record: Record, zone: str) -> None:
        data = record.original
        id_key, amount_key, currency_key, date_key, state_key = self.fields
        values = {}

        def check(key, action):
            raw = data.get(key)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                record.errors.append(Issue("MISSING_FIELD", key, "Campo obligatorio ausente, nulo o vacío."))
                return
            try:
                values[key] = action()
            except (ValueError, TypeError) as exc:
                record.errors.append(Issue("INVALID_FIELD", key, str(exc)))

        check(id_key, lambda: identifier(data.get(id_key)))
        if currency_key:
            check(currency_key, lambda: currency(data.get(currency_key)))
            code = values.get(currency_key)
        else:
            code = "EUR" if isinstance(data.get(amount_key), str) and data[amount_key].strip().startswith("€") else None
            if code is None:
                record.errors.append(Issue("INVALID_CURRENCY", amount_key, "Se requiere el símbolo € para inferir EUR."))
        # Validar también el formato del monto si la moneda es inválida.
        check(amount_key, lambda: amount(data.get(amount_key), code or "USD", self.name == "source_b", self.name == "source_c"))
        check(date_key, lambda: date(data.get(date_key), self.name, zone))

        def state():
            raw = data.get(state_key)
            if not isinstance(raw, str) or raw.strip().lower() not in self.states:
                raise ValueError("Estado ausente o desconocido.")
            return self.states[raw.strip().lower()]
        check(state_key, state)
        if date_key in values and values[date_key][1]:
            record.warnings.append(Issue("ASSUMED_TIMEZONE", date_key, f"Fecha sin zona: se asumió {zone}."))
        if not record.errors:
            record.normalized = Transaction(values[id_key], values[amount_key], code,
                                            values[date_key][0], values[state_key], self.name)


ADAPTERS = (
    Adapter("source_a", frozenset({"id", "currency", "timestamp", "status"}),
            ("id", "amount", "currency", "timestamp", "status"), dict(STATES)),
    Adapter("source_b", frozenset({"transaction_id", "total", "currency_code", "created_at", "state"}),
            ("transaction_id", "total", "currency_code", "created_at", "state"), dict(STATES)),
    Adapter("source_c", frozenset({"ref", "date", "result"}),
            ("ref", "amount", None, "date", "result"), dict(STATES)),
)
