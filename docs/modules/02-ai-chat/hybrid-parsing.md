# Hybrid reminder parsing

Chat reminders are parsed in three layers before creating a draft.

## Architecture

```
User message
    │
    ▼
Layer 1 — Rules (regex, keywords, intent, repeat, reminder matching)
    │
    ▼
Layer 2 — Date/time NLP (dateparser + parsedatetime + phrase rules)
    │
    ▼
Confident enough? ──yes──► Normalized draft (no LLM cost)
    │
    no
    ▼
Layer 3 — LLM (existing gateway, with rule hints in the prompt)
    │
    ▼
Normalized draft (or rule fallback if LLM fails)
```

## Layer details

| Layer | Module | Technology |
|-------|--------|------------|
| 1 | `ai_service/parsing/layer1_rules.py` | Regex, keyword intents, repeat aliases, fuzzy reminder match for edits |
| 2 | `ai_service/parsing/layer2_datetime.py` | `dateparser` (chrono-style), `parsedatetime`, named times (`after lunch`, `tonight`) |
| 3 | `ai_service/parsing/layer3_llm.py` | `AIRouter` multi-provider LLM |

User timezone from `users.timezone` is passed from `POST /chat` into Layer 2.

## When the LLM runs

The LLM is **skipped** when rules produce:

- A clear task (≥ 2 characters)
- No ambiguities (e.g. bare `at 3` without am/pm)
- Enough structure for chat to continue (`needs_time` is OK)

The LLM is **used** for:

- Ambiguous times
- Missing/unclear tasks
- `edit_saved` when no reminder match
- Complex phrasing rules did not resolve

## Logs

Filter backend logs:

```text
event=hybrid_parse
event=hybrid_parse_rule_hit
event=ai_layer3_request
event=chat_parse_result parser_layer=layer2
```

`parser_layer` values: `layer1`, `layer2`, `layer3`.

## Dependencies

```bash
pip install dateparser parsedatetime
```

Already listed in `backend/requirements.txt`.

## Optional future integrations

Not required today; hooks are documented for later:

| Tool | Role | Status |
|------|------|--------|
| **Duckling** | HTTP date entity service | Not wired — add optional `DUCKLING_URL` client in Layer 2 |
| **spaCy** | NER / noun phrases for task | Not required — Layer 1 regex covers MVP |
| **chrono** | JS library | Replaced by `dateparser` in Python |

## Tests

```bash
cd backend
pip install -r requirements.txt pytest pytest-asyncio
pytest tests/test_hybrid_parsing.py -q
```

## Examples handled without LLM

- `Remind me to buy milk tomorrow at 3pm`
- `Call mom at 9am`
- `Team meeting in 2 hours`
- `Remind me to take medicine every day at 8am`
- `make it 9pm` (with pending draft from prior turn)
- `Change my gym reminder to 7pm` (when gym reminder exists in list)
