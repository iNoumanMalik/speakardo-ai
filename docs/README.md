# Speakardo Documentation

Where every document lives, and which one wins when two disagree.

## Structure

```
docs/
├── README.md                            ← this index
├── product/                             WHAT we build and WHY
│   ├── prd.md                           Product requirements: vision, users, positioning
│   ├── srs.md                           Software requirements v1.1: modules, data model, APIs
│   ├── roadmap.md                       Phases and build order (v1.1)
│   └── exports/                         PDF snapshots of v1.0 (outdated, reference only)
├── modules/                             HOW each module is built
│   ├── 02-ai-chat/
│   │   └── hybrid-parsing.md            Rules → dateparser → LLM reminder parsing
│   ├── 03-reminders/
│   │   └── local-time-reminders.md      Wall-clock scheduling across timezones
│   └── 08-ai-memory/
│       ├── blueprint.md  (+ .pdf)       Vision, research review, roadmap. Read first
│       └── design.md                    Engineering spec: schema, APIs, milestones 8.0–8.4
└── setup/                               Running and debugging locally
    ├── debugging.md
    ├── email-auth.md
    └── google-auth.md
```

## Source of truth

1. **Markdown is the source of truth.** PDFs are exports and can lag behind.
2. **The more specific document wins:** `modules/<nn>-<name>/design.md` → `product/srs.md` → `product/prd.md`. If two disagree, follow the more specific one and fix the other in the same change.
3. **Build order** comes from `product/roadmap.md` (Revision 1.1).

## Module status

| # | Module | Status | Design docs |
| --- | --- | --- | --- |
| 1 | Authentication | Done | `product/srs.md` |
| 2 | AI Chat Assistant | Done for reminders; conversational chat arrives in 8.0–8.1 | `modules/02-ai-chat/` |
| 3 | Reminder Management | Done | `modules/03-reminders/` |
| 4 | Notifications | Done | `product/srs.md` |
| 8 | AI Memory System | 8.0 Foundations built. 8.1a Remember and forget built. **8.1b Understand any message built**; next: 8.1c Measure it (eval set) | `modules/08-ai-memory/` |
| 9 | Calendar Integration | After Module 8 | — |
| 7 | Voice Assistant | After Calendar | — |
| 5, 6 | Shared Reminders, Team Workspaces | Later | — |
| 10–12 | Scheduling, Autonomous, Analytics | Later | — |

## Conventions for new docs

- A new module gets `modules/<nn>-<kebab-name>/design.md` (add `blueprint.md` when strategy needs explaining).
- Lowercase kebab-case filenames, no spaces (macOS ignores case, so never create names differing only by case).
- How-to and environment guides go in `setup/`.
- Put the date and version at the top of every spec, and update the Module status table when a module starts or ships.
