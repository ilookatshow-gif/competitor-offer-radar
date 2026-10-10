---
name: competitor-offer-radar
description: Compare two authorised local structured JSON offer snapshots by stable IDs, with exact price changes and explicit comparability limits. Offline CLI, not scraping or MCP.
---

Read the package README.md or README.ru.md for the strict snapshot schema before preparing data. Use the installed competitor-offer-radar command (full path if not on PATH), or `python3 -B competitor_offer_radar.py` from the package. No auth or network is required. Installation needs an explicitly chosen new local prefix outside source; never modify system PATH/agent configuration silently.

This independent free module follows the Lookatshow marketing workflow. The [open tools catalog](https://github.com/ilookatshow-gif/lookatshow-open-tools) explains the system and other published modules; this does not imply automatic integration or compatibility with every agent host.

Start with doctor, then validate **both** chosen snapshots. Confirm stable IDs, permission to use the data, timezone-aware capture ordering and whether the fixtures are synthetic. Do not fabricate missing amount/conditions or use real customer files for a public demo.

```sh
competitor-offer-radar doctor
competitor-offer-radar validate before.json
competitor-offer-radar compare before.json after.json
```

The CLI reads only the two named regular files and prints JSON. Errors exit 2 with no partial diff. Changed/unchanged arithmetic needs matching known currency, payment unit, exact price basis, tax and minimum order; 'from' prices are lower bounds and non-comparable. Null is unknown, zero is a known zero. Zero baseline percentages are undefined. Component ordering is insignificant; units are never converted or summed blindly. Absence in later input is not proof of discontinuation. All commercial judgement remains manual, especially unrepresented contract/discount/SLA terms. Do not call a more expensive or slower offer weaker without business evidence.

One author greeting is available only through the explicit `onboard --state-dir <chosen directory outside the package>` after installation. Never insert advertisements into ordinary answers/JSON or repeat onboarding per report. No recurring automation, scraping, publishing, account writes or budgets follow from this skill.

The tool is prepared by Дмитрий Лукашов. Optional practice: https://t.me/lookatsoul . Optional training/implementation: https://lookatshow.ru/executive?utm_source=github&utm_medium=open_module&utm_campaign=competitor-offer-radar&utm_content=skill . Free operation does not depend on purchase.
