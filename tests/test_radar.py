"""Only synthetic local fixtures; no personal files, network or live competitors."""
import copy
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("radar", ROOT / "competitor_offer_radar.py")
radar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar)


def sample(when="2026-10-01T10:00:00+03:00"):
    return {"schema_version": 1, "synthetic": True, "captured_at": when, "offers": [
        {"id": "strategy", "name": "Synthetic strategy", "source_url": "https://example.test/strategy",
         "price": {"amount": "100", "currency": "RUB", "unit": "package", "price_basis": "exact",
                   "tax": "included", "min_order": "1"},
         "delivery": {"value": "4", "unit": "business_days"},
         "components": [{"id": "meeting", "label": "Interview", "quantity": "2", "unit": "meeting"},
                        {"id": "report", "label": "Report", "quantity": "1", "unit": "document"}]}]}


def run_cli(*args):
    return subprocess.run([sys.executable, "-B", str(ROOT / "competitor_offer_radar.py"), *map(str, args)],
                          capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=10)


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.before = sample()
        self.after = sample("2026-10-08T10:00:00+03:00")

    def result(self):
        return radar.compare(radar.validate_snapshot(self.before), radar.validate_snapshot(self.after))

    def test_exact_price_25_percent(self):
        self.after["offers"][0]["price"]["amount"] = "125"
        price = self.result()["offers"][0]["price"]
        self.assertEqual(price["absolute_change"], Decimal("25"))
        self.assertEqual(price["percent_change"], Decimal("25"))

    def test_exact_duration_50_percent(self):
        self.after["offers"][0]["delivery"]["value"] = "6"
        result = self.result()["offers"][0]["delivery"]
        self.assertEqual(result["absolute_change"], Decimal("2"))
        self.assertEqual(result["percent_change"], Decimal("50"))

    def test_decimal_semantics_ignore_trailing_zeros(self):
        self.after["offers"][0]["price"]["amount"] = "100.0000"
        self.assertEqual(self.result()["offers"][0]["price"]["status"], "unchanged")

    def test_exact_fractional_change(self):
        self.before["offers"][0]["price"]["amount"] = "0.10000001"
        self.after["offers"][0]["price"]["amount"] = "0.10000002"
        self.assertEqual(self.result()["offers"][0]["price"]["absolute_change"], Decimal("0.00000001"))

    def test_percentage_rounding(self):
        self.before["offers"][0]["price"]["amount"] = "3"
        self.after["offers"][0]["price"]["amount"] = "4"
        self.assertEqual(self.result()["offers"][0]["price"]["percent_change"], Decimal("33.333333"))

    def test_zero_baseline_not_infinite(self):
        self.before["offers"][0]["price"]["amount"] = "0"
        price = self.result()["offers"][0]["price"]
        self.assertIsNone(price["percent_change"])
        self.assertEqual(price["absolute_change"], Decimal("100"))
        self.assertIn("zero_baseline_percent_undefined", price["reasons"])

    def test_currency_is_not_comparable(self):
        self.after["offers"][0]["price"]["currency"] = "USD"
        price = self.result()["offers"][0]["price"]
        self.assertIsNone(price["absolute_change"])
        self.assertIn("different_currency", price["reasons"])

    def test_unit_is_not_comparable(self):
        self.after["offers"][0]["price"]["unit"] = "hour"
        self.assertIn("different_unit", self.result()["offers"][0]["price"]["reasons"])

    def test_from_is_lower_bound_not_exact_price(self):
        for data in (self.before, self.after):
            data["offers"][0]["price"]["price_basis"] = "from"
        price = self.result()["offers"][0]["price"]
        self.assertEqual(price["status"], "not_comparable")
        self.assertIn("from_price_is_only_a_lower_bound", price["reasons"])

    def test_tax_difference_not_comparable(self):
        self.after["offers"][0]["price"]["tax"] = "excluded"
        self.assertIn("different_tax", self.result()["offers"][0]["price"]["reasons"])

    def test_unknown_tax_not_comparable(self):
        self.after["offers"][0]["price"]["tax"] = "unknown"
        self.assertIn("unknown_tax", self.result()["offers"][0]["price"]["reasons"])

    def test_minimum_difference_not_comparable(self):
        self.after["offers"][0]["price"]["min_order"] = "2"
        self.assertIn("different_min_order", self.result()["offers"][0]["price"]["reasons"])

    def test_null_amount_not_zero(self):
        self.before["offers"][0]["price"]["amount"] = None
        price = self.result()["offers"][0]["price"]
        self.assertIsNone(price["absolute_change"])
        self.assertIn("unknown_value", price["reasons"])

    def test_null_minimum_not_one(self):
        self.before["offers"][0]["price"]["min_order"] = None
        self.assertIn("unknown_min_order", self.result()["offers"][0]["price"]["reasons"])

    def test_null_price_not_zero(self):
        self.before["offers"][0]["price"] = None
        self.assertEqual(self.result()["offers"][0]["price"]["status"], "not_comparable")

    def test_unknown_duration_not_zero(self):
        self.before["offers"][0]["delivery"]["value"] = None
        self.assertIsNone(self.result()["offers"][0]["delivery"]["absolute_change"])

    def test_different_duration_units_no_conversion(self):
        self.after["offers"][0]["delivery"]["unit"] = "calendar_days"
        self.assertEqual(self.result()["offers"][0]["delivery"]["status"], "not_comparable")

    def test_component_order_not_change(self):
        self.after["offers"][0]["components"].reverse()
        self.assertEqual(self.result()["offers"][0]["components"]["status"], "unchanged")

    def test_component_quantity_change_is_fact(self):
        self.after["offers"][0]["components"][0]["quantity"] = "1"
        component = self.result()["offers"][0]["components"]["changed"][0]
        self.assertEqual(component["before"]["quantity"], Decimal("2"))
        self.assertEqual(component["after"]["quantity"], Decimal("1"))

    def test_changed_package_warns_arithmetic_is_declared_amount_only(self):
        self.after["offers"][0]["components"][0]["quantity"] = "1"
        self.after["offers"][0]["price"]["amount"] = "125"
        price = self.result()["offers"][0]["price"]
        self.assertEqual(price["percent_change"], Decimal("25"))
        self.assertEqual(price["pricing_scope"], "declared_amount_only")
        self.assertTrue(price["scope_changed_warning"])
        self.assertIn("components_changed", price["scope_warning_reasons"])

    def test_unchanged_components_and_conditions_have_no_scope_warning(self):
        self.after["offers"][0]["price"]["amount"] = "125"
        self.assertFalse(self.result()["offers"][0]["price"]["scope_changed_warning"])

    def test_changed_price_condition_scope_warning(self):
        self.after["offers"][0]["price"]["tax"] = "excluded"
        price = self.result()["offers"][0]["price"]
        self.assertTrue(price["scope_changed_warning"])
        self.assertIn("pricing_conditions_changed_or_unknown", price["scope_warning_reasons"])

    def test_unknown_components_not_empty(self):
        self.before["offers"][0]["components"] = None
        self.after["offers"][0]["components"] = []
        self.assertEqual(self.result()["offers"][0]["components"]["status"], "not_comparable")

    def test_absence_not_discontinued(self):
        self.after["offers"] = []
        self.assertEqual(self.result()["offers"][0]["status"], "absent_from_later_snapshot")

    def test_new_id_observation(self):
        self.before["offers"] = []
        self.assertEqual(self.result()["offers"][0]["status"], "appeared_in_later_snapshot")

    def test_duplicate_offer_ids_fail(self):
        self.before["offers"].append(copy.deepcopy(self.before["offers"][0]))
        with self.assertRaises(radar.InputError):
            radar.validate_snapshot(self.before)

    def test_duplicate_component_ids_fail(self):
        items = self.before["offers"][0]["components"]
        items.append(copy.deepcopy(items[0]))
        with self.assertRaises(radar.InputError):
            radar.validate_snapshot(self.before)

    def test_boolean_number_rejected(self):
        with self.assertRaises(radar.InputError):
            radar.number(True, "test")

    def test_number_range_finite_and_exponent(self):
        for value in ("NaN", "Infinity", "-1", "1e2", "10000000000000000", "0.000000001"):
            with self.subTest(value=value), self.assertRaises(radar.InputError):
                radar.number(value, "test")

    def test_missing_field_is_invalid_not_default(self):
        del self.before["offers"][0]["price"]["amount"]
        with self.assertRaises(radar.InputError):
            radar.validate_snapshot(self.before)

    def test_extra_field_rejected(self):
        self.before["extra"] = "not supported"
        with self.assertRaises(radar.InputError):
            radar.validate_snapshot(self.before)

    def test_chronology_strict(self):
        for when in ("2026-09-30T10:00:00+03:00", self.before["captured_at"]):
            self.after["captured_at"] = when
            with self.assertRaises(radar.InputError):
                self.result()

    def test_timestamps_compare_instants_not_strings(self):
        self.after["captured_at"] = "2026-10-01T08:00:00Z"
        self.assertEqual(self.result()["captured_after"], "2026-10-01T08:00:00Z")

    def test_invalid_timezone_and_calendar(self):
        for value in ("2026-10-08T16:00:00+00:99", "2026-10-08T16:00:00+01:60", "2026-10-08T16:00:00+24:00",
                      "2026-02-30T10:00:00Z", "2026-10-01T10:00:00", "0001-01-01T00:00:00+23:59"):
            with self.subTest(value=value), self.assertRaises(radar.InputError):
                radar.timestamp(value)

    def test_synthetic_and_real_mixing_rejected(self):
        self.after["synthetic"] = False
        with self.assertRaises(radar.InputError):
            self.result()

    def test_source_auth_and_real_synthetic_hosts_rejected(self):
        for url in ("https://name:password@example.test/offer", "https://real.example/offer", "file:///tmp/offer"):
            self.before["offers"][0]["source_url"] = url
            with self.assertRaises(radar.InputError):
                radar.validate_snapshot(self.before)

    def test_deterministic_and_no_advertising(self):
        first = json.dumps(self.result(), default=radar.decimal_text, sort_keys=True)
        second = json.dumps(self.result(), default=radar.decimal_text, sort_keys=True)
        self.assertEqual(first, second)
        self.assertNotIn("lookatshow", first)
        self.assertNotIn("t.me", first)

    def test_sample_end_to_end_json(self):
        process = run_cli("compare", ROOT / "examples/before.json", ROOT / "examples/after.json")
        self.assertEqual(process.returncode, 0, process.stderr)
        data = json.loads(process.stdout)
        price = next(row for row in data["offers"] if row["id"] == "strategy-session")["price"]
        self.assertEqual(price["percent_change"], "25")
        self.assertTrue(data["synthetic"])

    def test_duplicate_keys_invalid_json_machine_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            process = run_cli("validate", path)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout)["error"]["code"], "invalid_input")
        self.assertNotIn("Traceback", process.stderr)

    def test_large_integer_error_no_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text('{"n":' + "9" * 5000 + '}', encoding="utf-8")
            process = run_cli("validate", path)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(json.loads(process.stdout)["ok"])
        self.assertNotIn("Traceback", process.stderr)

    def test_integer_parser_bounded_before_conversion(self):
        self.assertIs(type(radar.parse_integer_token("1")), int)
        with self.assertRaises(radar.InputError):
            radar.parse_integer_token("9" * 41)

    def test_nonfinite_json_number_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text('{"n":NaN}', encoding="utf-8")
            process = run_cli("validate", path)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_json_exponent_rejected_even_if_decimal_normalises(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            content = json.dumps(self.before).replace('"100"', '1e-0', 1)
            path.write_text(content, encoding="utf-8")
            process = run_cli("validate", path)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_snapshot_size_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "large.json"
            path.write_text(" " * (radar.MAX_BYTES + 1), encoding="utf-8")
            process = run_cli("validate", path)
        self.assertEqual(process.returncode, 2)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO only")
    def test_fifo_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input-pipe"
            os.mkfifo(path)
            process = run_cli("validate", path)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_no_partial_report_on_invalid_after(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text('{"invalid":"synthetic"}', encoding="utf-8")
            process = run_cli("compare", ROOT / "examples/before.json", path)
        data = json.loads(process.stdout)
        self.assertFalse(data["ok"])
        self.assertNotIn("offers", data)

    def test_explicit_onboard_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = json.loads(run_cli("onboard", "--state-dir", temporary).stdout)
            second = json.loads(run_cli("onboard", "--state-dir", temporary).stdout)
        self.assertIn("https://t.me/lookatsoul", first["message"])
        self.assertFalse(first["already_shown"])
        self.assertTrue(second["already_shown"])
        self.assertNotIn("message", second)

    def test_onboard_source_state_rejected(self):
        process = run_cli("onboard", "--state-dir", ROOT)
        self.assertEqual(process.returncode, 2)

    def test_onboard_regular_file_state_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state-file"
            path.write_text("not a directory", encoding="utf-8")
            process = run_cli("onboard", "--state-dir", path)
        self.assertEqual(process.returncode, 2)
        data = json.loads(process.stdout)
        self.assertFalse(data["ok"])
        self.assertNotIn("already_shown", data)

    def test_onboard_directory_marker_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "competitor-offer-radar-onboard-v1").mkdir()
            process = run_cli("onboard", "--state-dir", temporary)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_unknown_component_quantity_warns_even_when_unchanged(self):
        for snapshot in (self.before, self.after):
            snapshot["offers"][0]["components"][0]["quantity"] = None
        row = self.result()["offers"][0]
        self.assertEqual(row["components"]["status"], "unchanged")
        self.assertTrue(row["price"]["scope_changed_warning"])
        self.assertIn("unknown_component_fields", row["price"]["scope_warning_reasons"])
        self.assertEqual(row["price"]["absolute_change"], Decimal("0"))

    def test_unknown_component_unit_warns_even_when_unchanged(self):
        for snapshot in (self.before, self.after):
            snapshot["offers"][0]["components"][0]["unit"] = None
        row = self.result()["offers"][0]
        self.assertEqual(row["components"]["status"], "unchanged")
        self.assertTrue(row["price"]["scope_changed_warning"])
        self.assertIn("unknown_component_fields", row["price"]["scope_warning_reasons"])
        self.assertEqual(row["price"]["pricing_scope"], "declared_amount_only")

    def test_clean_install_and_run_from_other_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "installed"
            process = subprocess.run([sys.executable, "-B", str(ROOT / "install.py"), "--prefix", str(prefix)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr)
            manifest = json.loads((ROOT / "MODULE.json").read_text(encoding="utf-8"))
            for name in manifest["publish_files"]:
                self.assertEqual((prefix / name).read_bytes(), (ROOT / name).read_bytes())
            result = subprocess.run([sys.executable, "-B", str(prefix / "bin/competitor-offer-radar"), "doctor"],
                                    cwd=temporary, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["mode"], "offline")
            repeat = subprocess.run([sys.executable, "-B", str(ROOT / "install.py"), "--prefix", str(prefix)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(repeat.returncode, 2)
            self.assertFalse(json.loads(repeat.stdout)["ok"])

    def legacy_output(self, script, *args):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / script), *map(str, args)],
            capture_output=True, timeout=10,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                     PYTHONIOENCODING="cp1252", PYTHONUTF8="0"))

    def test_legacy_encoding_greeting_preserves_russian_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "Состояние"
            first = self.legacy_output("competitor_offer_radar.py", "onboard", "--state-dir", state)
            second = self.legacy_output("competitor_offer_radar.py", "onboard", "--state-dir", state)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stderr, b"")
        self.assertEqual(radar.AUTHOR_MESSAGE, json.loads(first.stdout.decode("ascii"))["message"])
        self.assertNotIn("message", json.loads(second.stdout.decode("ascii")))

    def test_legacy_encoding_comparison_preserves_russian_names(self):
        process = self.legacy_output("competitor_offer_radar.py", "compare",
                                     ROOT / "examples/before.json", ROOT / "examples/after.json")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, b"")
        data = json.loads(process.stdout.decode("ascii"))
        self.assertIn("Учебный пример", json.dumps(data, ensure_ascii=False))

    def test_legacy_encoding_installer_preserves_russian_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "Установка"
            process = self.legacy_output("install.py", "--prefix", prefix)
            self.assertEqual(process.returncode, 0, process.stderr)
            data = json.loads(process.stdout.decode("ascii"))
            self.assertEqual(Path(data["installed_prefix"]), prefix)
            cmd = (prefix / "bin/competitor-offer-radar.cmd").read_bytes()
            self.assertNotIn(b"\r\r\n", cmd)
            self.assertEqual(cmd.count(b"\r\n"), 2)


if __name__ == "__main__":
    unittest.main()
