#!/usr/bin/env python3
"""Original, offline structured offer comparison. No HTTP client or MCP transport."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit

VERSION = "0.1.0"
MAX_BYTES = 2_000_000
MAX_OFFERS = 2000
AUTHOR_MESSAGE = (
    "Инструмент подготовлен Дмитрием Лукашовым. Практика ИИ для бизнеса: "
    "https://t.me/lookatsoul . Обучение и внедрение на своих процессах: "
    "https://lookatshow.ru/executive?utm_source=github&utm_medium=open_module"
    "&utm_campaign=competitor-offer-radar&utm_content=onboard . "
    "Бесплатный инструмент работает без покупки ядра."
)


class InputError(ValueError):
    """An input contract violation, without echoing source data."""


def require(condition, message):
    if not condition:
        raise InputError(message)


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected),
            label + ": missing or unsupported fields")


def text(value, label, nullable=False):
    if nullable and value is None:
        return None
    require(isinstance(value, str) and 0 < len(value) <= 500 and value == value.strip()
            and not any(ord(c) < 32 for c in value), label + ": invalid text")
    return value


def number(value, label):
    if value is None:
        return None
    require(not isinstance(value, bool) and isinstance(value, (str, int, Decimal)),
            label + ": expected decimal number, decimal string, or null")
    spelling = str(value)
    require(len(spelling) <= 40 and re.fullmatch(r"\d+(?:\.\d+)?", spelling) is not None,
            label + ": expected non-negative decimal without exponent")
    try:
        result = Decimal(spelling)
    except InvalidOperation:
        raise InputError(label + ": invalid decimal")
    require(result.is_finite() and result.adjusted() <= 15
            and result.as_tuple().exponent >= -8, label + ": decimal outside supported range")
    return result


def decimal_text(value):
    if value is None:
        return None
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def timestamp(value):
    value = text(value, "captured_at")
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value)
            is not None, "captured_at: expected ISO timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InputError("captured_at: invalid timestamp")
    require(parsed.utcoffset() is not None, "captured_at: timezone required")
    try:
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise InputError("captured_at: timestamp outside supported calendar range")


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def invalid_constant(_):
    raise InputError("non-finite JSON number")


def parse_decimal_token(value):
    require("e" not in value.lower() and len(value) <= 40, "JSON number: exponent or excessive length")
    return Decimal(value)


def parse_integer_token(value):
    require(len(value) <= 40, "JSON integer: excessive length")
    return int(value)


def validate_price(price):
    if price is None:
        return None
    keys(price, ("amount", "currency", "unit", "price_basis", "tax", "min_order"), "price")
    amount = number(price["amount"], "price.amount")
    minimum = number(price["min_order"], "price.min_order")
    require(minimum is None or minimum > 0, "price.min_order: must be positive or unknown")
    currency = text(price["currency"], "price.currency", True)
    require(currency is None or re.fullmatch(r"[A-Z]{3}", currency) is not None,
            "price.currency: expected three uppercase letters or null")
    unit = text(price["unit"], "price.unit", True)
    basis, tax = price["price_basis"], price["tax"]
    require(basis in ("exact", "from", None), "price.price_basis: exact/from/null required")
    require(tax in ("included", "excluded", "unknown"), "price.tax: invalid tax basis")
    return dict(amount=amount, currency=currency, unit=unit, price_basis=basis, tax=tax, min_order=minimum)


def validate_delivery(delivery):
    if delivery is None:
        return None
    keys(delivery, ("value", "unit"), "delivery")
    require(delivery["unit"] in ("calendar_days", "business_days", "weeks", "months", None),
            "delivery.unit: unsupported unit")
    return {"value": number(delivery["value"], "delivery.value"), "unit": delivery["unit"]}


def validate_components(components):
    if components is None:
        return None
    require(isinstance(components, list) and len(components) <= 200, "components: expected bounded list/null")
    result = {}
    for item in components:
        keys(item, ("id", "label", "quantity", "unit"), "component")
        component_id = text(item["id"], "component.id")
        require(component_id not in result, "duplicate component id")
        result[component_id] = dict(id=component_id, label=text(item["label"], "component.label"),
                                   quantity=number(item["quantity"], "component.quantity"),
                                   unit=text(item["unit"], "component.unit", True))
    return [result[key] for key in sorted(result)]


def validate_snapshot(data):
    keys(data, ("schema_version", "synthetic", "captured_at", "offers"), "snapshot")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "unsupported schema_version")
    require(type(data["synthetic"]) is bool, "synthetic: boolean required")
    captured = timestamp(data["captured_at"])
    require(isinstance(data["offers"], list) and len(data["offers"]) <= MAX_OFFERS,
            "offers: expected bounded list")
    offers = {}
    for item in data["offers"]:
        keys(item, ("id", "name", "source_url", "price", "delivery", "components"), "offer")
        offer_id = text(item["id"], "offer.id")
        require(offer_id not in offers, "duplicate offer id")
        source = text(item["source_url"], "source_url")
        try:
            url = urlsplit(source)
            port = url.port
        except ValueError:
            raise InputError("source_url: invalid URL")
        require(url.scheme in ("https", "http") and url.hostname and url.username is None
                and url.password is None and not url.fragment and (port is None or 1 <= port <= 65535),
                "source_url: HTTP(S) URL without credentials or fragment required")
        require(not data["synthetic"] or url.hostname == "example.test",
                "synthetic source_url must use example.test")
        offers[offer_id] = dict(id=offer_id, name=text(item["name"], "offer.name"), source_url=source,
                               price=validate_price(item["price"]), delivery=validate_delivery(item["delivery"]),
                               components=validate_components(item["components"]))
    return {"synthetic": data["synthetic"], "captured_at": captured, "offers": offers}


def load_snapshot(path):
    try:
        require(Path(path).is_file(), "snapshot must be a regular local file")
        descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as source:
            require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "snapshot must be a regular local file")
            raw = source.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, "snapshot exceeds 2 MB")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
                          parse_float=parse_decimal_token, parse_int=parse_integer_token, parse_constant=invalid_constant)
    except InputError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise InputError("cannot read valid UTF-8 JSON snapshot")
    return validate_snapshot(data)


def comparable_diff(before, after, numeric, conditions):
    reasons = []
    if before is None or after is None:
        reasons.append("missing_measurement")
    else:
        if before[numeric] is None or after[numeric] is None:
            reasons.append("unknown_value")
        if "price_basis" in conditions and "from" in (before["price_basis"], after["price_basis"]):
            reasons.append("from_price_is_only_a_lower_bound")
        for field in conditions:
            left, right = before[field], after[field]
            if left is None or right is None or (field == "tax" and "unknown" in (left, right)):
                reasons.append("unknown_" + field)
            elif left != right:
                reasons.append("different_" + field)
    result = {"before": before, "after": after, "absolute_change": None, "percent_change": None,
              "status": "not_comparable", "reasons": reasons}
    if not reasons:
        left, right = before[numeric], after[numeric]
        result["status"] = "unchanged" if before == after else "changed"
        with localcontext() as context:
            context.prec = 40
            result["absolute_change"] = right - left
            if left != 0:
                result["percent_change"] = ((right - left) * 100 / left).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            else:
                result["reasons"] = ["zero_baseline_percent_undefined"]
    return result


def component_diff(before, after):
    if before is None or after is None:
        return {"status": "not_comparable", "before": before, "after": after,
                "reasons": ["unknown_components"]}
    left = {item["id"]: item for item in before}
    right = {item["id"]: item for item in after}
    changed = [{"id": key, "before": left[key], "after": right[key]}
               for key in sorted(left.keys() & right.keys()) if left[key] != right[key]]
    return {"status": "unchanged" if before == after else "changed",
            "appeared_ids": sorted(right.keys() - left.keys()),
            "absent_later_ids": sorted(left.keys() - right.keys()), "changed": changed}


def compare(before, after):
    require(before["captured_at"] < after["captured_at"], "after snapshot must be strictly later than before")
    require(before["synthetic"] == after["synthetic"], "cannot mix synthetic and non-synthetic snapshots")
    rows = []
    left, right = before["offers"], after["offers"]
    for key in sorted(left.keys() | right.keys()):
        if key not in left or key not in right:
            rows.append({"id": key, "status": "appeared_in_later_snapshot" if key in right else "absent_from_later_snapshot",
                         "observed_offer": right.get(key, left.get(key)), "manual_review": True})
            continue
        old, new = left[key], right[key]
        components = component_diff(old["components"], new["components"])
        price = comparable_diff(old["price"], new["price"], "amount", ("currency", "unit", "price_basis", "tax", "min_order"))
        warnings = []
        if components["status"] != "unchanged":
            warnings.append("components_changed" if components["status"] == "changed" else "components_unknown")
        if any(item["quantity"] is None or item["unit"] is None
               for collection in (old["components"], new["components"])
               if collection is not None for item in collection):
            warnings.append("unknown_component_fields")
        if any(reason.startswith(("different_", "unknown_")) or reason == "missing_measurement" for reason in price["reasons"]):
            warnings.append("pricing_conditions_changed_or_unknown")
        price.update(pricing_scope="declared_amount_only", scope_changed_warning=bool(warnings), scope_warning_reasons=warnings)
        rows.append({"id": key, "status": "observed_in_both_snapshots", "manual_review": True,
                     "source_before": old["source_url"], "source_after": new["source_url"],
                     "name_before": old["name"], "name_after": new["name"],
                     "price": price,
                     "delivery": comparable_diff(old["delivery"], new["delivery"], "value", ("unit",)),
                     "components": components})
    return {"ok": True, "schema_version": 1, "synthetic": before["synthetic"],
            "captured_before": before["captured_at"].isoformat().replace("+00:00", "Z"),
            "captured_after": after["captured_at"].isoformat().replace("+00:00", "Z"),
            "offers": rows, "manual_review_required": True,
            "limitations": ["Absence means absence from a supplied snapshot, not a discontinued product.",
                            "Conditions not represented here (discounts, payment timing, region, contract terms) require manual review.",
                            "No winner, business value, profitability, or demand conclusion is calculated."]}


def onboard(state_dir):
    root = Path(state_dir).expanduser().resolve()
    package = Path(__file__).resolve().parent
    require(root != package and package not in root.parents, "onboard state must be outside source package")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise InputError("cannot create local onboarding state directory")
    require(root.is_dir(), "onboard state must be a directory")
    marker_path = root / "competitor-offer-radar-onboard-v1"
    try:
        descriptor = os.open(str(marker_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        require(marker_path.is_file() and not marker_path.is_symlink(),
                "onboarding marker must be a regular local file")
        return {"ok": True, "already_shown": True}
    except OSError:
        raise InputError("cannot create local onboarding marker")
    try:
        with os.fdopen(descriptor, "w") as marker:
            marker.write("shown\n")
    except OSError:
        raise InputError("cannot store local onboarding marker; inspect state directory before retry")
    return {"ok": True, "already_shown": False, "message": AUTHOR_MESSAGE}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two authorised local offer snapshots. JSON output; no network.")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Report offline runtime; no auth/config needed")
    validate = sub.add_parser("validate", help="Validate one strict snapshot, without echoing offers")
    validate.add_argument("snapshot")
    diff = sub.add_parser("compare", help="Read two snapshots; output observed changes, not commercial conclusions")
    diff.add_argument("before")
    diff.add_argument("after")
    welcome = sub.add_parser("onboard", help="Explicit author greeting once per local state directory")
    welcome.add_argument("--state-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = {"ok": sys.version_info >= (3, 9), "version": VERSION, "mode": "offline", "auth_required": False,
                      "network": False, "telemetry": False, "python": ".".join(map(str, sys.version_info[:3]))}
        elif args.command == "validate":
            data = load_snapshot(args.snapshot)
            result = {"ok": True, "offer_count": len(data["offers"]), "synthetic": data["synthetic"],
                      "captured_at": data["captured_at"].isoformat().replace("+00:00", "Z")}
        elif args.command == "compare":
            result = compare(load_snapshot(args.before), load_snapshot(args.after))
        else:
            result = onboard(args.state_dir)
        # ASCII JSON escapes preserve Unicode after parsing, even when a
        # Windows pipe uses a legacy encoding rather than UTF-8.
        print(json.dumps(result, ensure_ascii=True, indent=2, default=decimal_text, allow_nan=False))
        return 0 if result["ok"] else 2
    except InputError as error:
        print(json.dumps({"ok": False, "error": {"code": "invalid_input", "message": str(error)}}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
