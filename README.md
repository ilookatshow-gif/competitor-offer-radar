# Compare competitor offers: prices, delivery and scope

[Русская инструкция](README.ru.md)

[![Portable installation](https://github.com/ilookatshow-gif/competitor-offer-radar/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ilookatshow-gif/competitor-offer-radar/actions/workflows/ci.yml)

A free standalone Python 3.9+ CLI compares two authorised structured JSON snapshots by stable offer IDs. It records observed price, delivery and component changes, their source URLs and capture timestamps. No network, scraping, credentials, telemetry, MCP transport or paid core required. A changed price is not automatically a weaker offer or a winner. Original, AI-assisted implementation; see NOTICE.md and MIT LICENSE.

A module of **Lookatshow, a unified marketing operating system for AI agents**. Browse the [open tools catalog](https://github.com/ilookatshow-gif/lookatshow-open-tools). For local Yandex Direct placement reports, use the standalone [direct-report-audit](https://github.com/ilookatshow-gif/direct-report-audit). No paid core is required; an automatic integration between these modules is not supplied.

## Run a real educational example

```sh
python3 -B competitor_offer_radar.py doctor
python3 -B competitor_offer_radar.py validate examples/before.json
python3 -B competitor_offer_radar.py compare examples/before.json examples/after.json
python3 -B -m unittest discover -s tests -v
```

The **fictional synthetic** strategy-session increases from 10,000 to 12,500 RUB per package (+2,500/+25%) and from four to six business days (+2/+50%). Interview quantity changes from two to one. `starter` is absent from the later supplied snapshot; `audit` appears there. None of this proves a real launch, discontinuation or decline in customer value. The example.test URLs are not visited.

This example sets `scope_changed_warning=true`: the package changed, so +25% is not a pure price increase for equivalent work. Unknown component `quantity` or `unit` also sets the `unknown_component_fields` warning, even when both snapshots contain identical null values.

## Installation, onboarding, removal

The stdlib installer copies only MODULE.json publish_files into a **new prefix outside this source package**, creates local launchers and never changes system PATH or agent configuration. It fails if the prefix already exists. From the source directory:

```sh
python3 -B install.py --prefix ../offer-radar-installed
../offer-radar-installed/bin/competitor-offer-radar doctor
../offer-radar-installed/bin/competitor-offer-radar onboard --state-dir ../offer-radar-state
```

Use the installed launcher's full path from any working directory, or add its bin to your own PATH deliberately. Windows can run `python competitor_offer_radar.py ...` or installed `bin\competitor-offer-radar.cmd`. The launcher requires the supported `python` interpreter on PATH. Python must already be installed; no dependency downloads.

Only explicit onboard displays an author greeting once per selected state directory, which must be outside the source/installed package. It stores only `competitor-offer-radar-onboard-v1`; subsequent calls report already_shown without repeating advertising. This is directory-local, not person identification; changing/removing the marker can repeat the greeting. Ordinary reports have no advertisements. To uninstall, move **only your chosen install prefix** and any chosen state directory to trash. Remove a manually added PATH/skill entry if applicable. No background service exists. A failed copy may leave a partial prefix: inspect before retrying; never delete unrelated files automatically.

## Strict input contract

See the complete executable JSON examples and detailed [RU schema](README.ru.md). A snapshot requires exactly schema_version=1 (integer), synthetic (boolean), captured_at (ISO timezone-aware timestamp with seconds), and offers (up to 2,000). The after timestamp must be strictly later by UTC instant. Never mix synthetic and non-synthetic snapshots. Duplicate JSON keys, offer IDs and component IDs or unsupported fields fail closed.

Each offer has exactly id, name, source_url, price, delivery, components. Stable IDs must mean the same product across captures; no name guessing or cross-ID ranking. HTTP(S) source URLs may not contain credentials/fragments; synthetic URLs must use example.test. No URLs are fetched or authenticated. Do not use secret/signed URLs. Real input must be authorised; reports echo offer data and must stay private.

- price: null or `{amount,currency,unit,price_basis,tax,min_order}`. Numeric fields accept decimal strings/JSON numbers/null, never booleans: nonnegative, no exponent, up to 16 integer digits and eight fractional places. Decimal strings avoid editor precision loss. min_order is positive/null and means minimum number of the same payment unit; use 1 when the minimum is one, not null. Null always means unknown.
- Known amount plus **identical known currency/unit/price_basis/tax/min_order** are required for arithmetic price comparison. currency: three uppercase letters (not currency existence validation); unit: your consistent label. price_basis: exact/from/null; tax: included/excluded/unknown. A 'from' price is only a lower bound and always not_comparable, even when both use 'from'. No currency/unit conversions or hidden tax/minimum assumptions.
- delivery: null or `{value,unit}`. unit: calendar_days/business_days/weeks/months/null. Unknown values or different units are not_comparable. Delivery duration is not a quality score.
- components: null (unknown), [] (explicitly none listed) or up to 200 `{id,label,quantity,unit}` items. Compare stable IDs, ignore ordering. Changed label/quantity/unit is factual before/after, never summed across units or called a worse offer.

Discounts, payment timing, region, SLA, availability, exact package scope and contractual terms outside the schema require manual review. Identical `package` labels do not prove equivalent packages; inspect components. Price output explicitly has `pricing_scope="declared_amount_only"`: arithmetic describes only the declared sum, not an equivalent unit of work. Changed/unknown components or pricing conditions set `scope_changed_warning=true` with reasons. The educational example has this warning: +25% is the sum change for a changed package, not proof of a pure price increase for an equivalent bundle. Absence only means absence from a supplied snapshot, not discontinued service. Source URLs/capture times record provenance supplied by you, not independently verified truth.

## Output, composability, errors

doctor/validate/compare/onboard always emit JSON to stdout. --help/--version use argparse text; argument errors use stderr/code 2. doctor reports ok/version/mode/auth_required/network/telemetry/python; validate reports ok/offer_count/synthetic/captured_at. compare reports ok/schema_version/synthetic/captured_before/captured_after/offers/manual_review_required/limitations. All offers require manual_review.

JSON output escapes non-ASCII characters as `\uXXXX`: parsing restores the original names and Russian greeting without depending on a console/pipe code page. Inputs remain UTF-8 JSON. This also applies to the installer result; no Unicode data is transliterated or discarded.

Common ID rows include source/name before/after; price/delivery have status (changed/unchanged/not_comparable), before/after, absolute_change, percent_change, reasons. Numeric output uses normalised decimal **strings**. Absolute differences are exact; percentages round HALF_UP to six decimal places and trim trailing zeros. With zero baseline, percent_change is null with an explicit reason, never Infinity. Components list appeared_ids/absent_later_ids/changed, or not_comparable when unknown. New/absent offer IDs use appeared_in_later_snapshot/absent_from_later_snapshot plus observed_offer.

Invalid input produces only `{ok:false,error:{code:"invalid_input",message:"..."}}` and exit 2, no partial comparison. Exit 0 is a completed local calculation, not savings, source authenticity or commercial success. Files must be local regular files, at most 2 MB; FIFO/devices are rejected. No config/auth required. No raw network escape hatch is supplied because this tool has no network service.

## Codex / Claude Code prompt

> Read README.md and AGENTS.md. Install into a new local prefix outside the source package; do not change system PATH. Run doctor, tests and both synthetic snapshots. Run one explicit onboard using a separate state directory. Compare my two authorised JSON snapshots. Do not invent missing values, fetch sites, access credentials or publish my data. Show observed changes and comparability limits, not a winner.

The companion skill lives in `skills/competitor-offer-radar/SKILL.md`. It is instructions, not a daemon or a tested integration with every agent client; no live competitor data or savings claims are made.

## Reproduce the installation check

```sh
python3 -B tests/smoke_install.py
```

The check installs into a new temporary path with spaces and Cyrillic characters, runs the **native** POSIX or Windows `.cmd` launcher from a different directory, compares synthetic snapshots, checks one-time onboarding, refuses an existing prefix, verifies installed file bytes and runs installed regression tests. Temporary data is deleted by this check, not your working files. The source tests also exercise a legacy cp1252 output stream.

[CI run details](https://github.com/ilookatshow-gif/competitor-offer-radar/actions/workflows/ci.yml) show separate jobs for Ubuntu 24.04/Python 3.9 and 3.12, Windows Server 2022/Python 3.12 and macOS 15/Python 3.12. A workflow definition or badge alone is not a passing run: inspect its exact commit, status and skipped tests. FIFO coverage is POSIX-only. CI does not prove compatibility with every OS, Python version or live agent host. These are current `main` checks; the immutable v0.1.0 release ZIP does not include this later encoding fix or CI helper. Use current source for these improvements; the old tag/ZIP is not overwritten.

## Author / business practice

Run the example and compare your own authorised snapshots for free. No subscription, contact details or paid core are required.

Prepared by **Дмитрий Лукашов (Dmitry Lukashov)**. [Practical business AI on Telegram](https://t.me/lookatsoul).

- Want to compare offers with an AI agent yourself? [Discuss personal training](https://lookatshow.ru/executive?utm_source=github&utm_medium=open_module&utm_campaign=competitor-offer-radar&utm_content=training). Learn to prepare comparable inputs, check observed changes and keep unknowns visible.
- Need a repeatable comparison process adapted to your company's data and workflow? [Discuss implementation](https://lookatshow.ru/ai-implementation/?utm_source=github&utm_medium=open_module&utm_campaign=competitor-offer-radar&utm_content=implementation). Project scope, access, acceptance criteria and cost are agreed separately; training does not include implementation. This free module remains an offline comparison tool, not a website scraper.
