# Speakardo Module 8: Memory & Intelligence Blueprint

_How Speakardo remembers, understands context, and acts at the right moment_

| | |
| --- | --- |
| Product | Speakardo AI life assistant |
| Version | 1.0, 26 September 2026 |
| Owner | Nouman |
| Status | Agreed direction; open decisions in section 12 |
| Engineering spec | docs/modules/08-ai-memory/design.md |


## 1. The idea in one page

Speakardo is an AI life assistant that understands what you say, remembers what matters about your life, and uses that to help you at the right moment.

> **Don't tell Speakardo when. Tell Speakardo what matters.**

**The moat is not the technology.** Anyone can add embeddings and a vector database. What competitors can't copy quickly is a structured, long-term understanding of each user's life (who matters to them, what they prefer, what they usually do, what they finished or missed), together with the trust that makes users willing to share it.

**Memory is not the assistant. It is one of four layers:**

- **Memory**: what Speakardo knows about the user.
- **Context**: what matters right now.
- **Reasoning**: what to do about it.
- **Action**: doing it (reminders, notifications, later calls and automations).

This document keeps what was right in the earlier research (Notion "Intelligence Core" pages and the ChatGPT discussion), fixes what was wrong or missing, and turns it into a build order that fits a one-person team.


## 2. Review of the research: what holds, what to fix

**What holds up:** five kinds of memory; the Memory, Context, Reasoning, Action split; a source, confidence, importance, lifespan and privacy level on every memory; PostgreSQL + pgvector instead of a separate vector database; autonomy levels; full user controls and an audit trail; and no over-engineering (no Pinecone, Redis, Kafka or multi-agent setups yet).

**What needs fixing before we build:**

| # | Issue in the research | Why it matters | Fix |
| --- | --- | --- | --- |
| 1 | Ranking multiplies relevance × importance × confidence × recency | One low factor wipes out a memory; a birthday saved last year scores near zero | Weighted sum; recency applies only to events and temporary facts |
| 2 | Says "don't use one memories table", then designs one table | Contradictory; splitting by kind makes search harder | Split by lifecycle, not kind: one table for stated facts; separate tables for habits, raw events and people |
| 3 | Learns from reminder behaviour, but there is no data for it | The reminders table stores only current state, not a history of completions, snoozes or dismissals | Start a reminder_events log in 8.0. You can't learn later from data you never collected |
| 4 | Confidence values such as 0.87 with no method | LLM self-reported confidence is poorly calibrated | Rules: stated 1.0, clearly implied 0.8, LLM-inferred at most 0.6; habits computed from repetitions |
| 5 | Habits detected from a few data points | False patterns ("you always gym at 6") annoy users and erode trust | At least 4 occurrences over 2+ weeks with low time variance, confirmed by the user before use |
| 6 | Every episode ("went to the gym yesterday") becomes memory | Floods memory with noise and raises cost | Keep episodes in chat history; promote only important or repeated facts |
| 7 | Location and geofences appear early (coffee shop, route to work) | Needs "Always" location, platform geofence limits, battery, store review and place data; feels creepy | Separate later module: user-defined places only, opt-in. Route-based ideas are V3+ |
| 8 | Wake and sleep times inferred | The app cannot observe sleep; this is guessing | Ask once in onboarding; refine from reminder behaviour later |
| 9 | ~18 tables including context_snapshots | Stored snapshots are an activity and location history: privacy risk and migration cost | Context is computed per request, never stored. 5 tables in 8A |
| 10 | Assumes chat can already hold a conversation | Today every message goes to the reminder parser and history isn't saved on the server | Conversational chat and stored history come first (8.0 to 8.1) |
| 11 | Examples call Sara the mother in one place and the sister in another | Shows the real problem: names are ambiguous | People as records with relationship and aliases (Ammi, Mom, my mother); ask when two match |
| 12 | No trust and safety engineering | Memories could reach 7 AI providers; "remember that you must..." can inject instructions; deletion must include embeddings | Provider allowlist; memories passed as data, never instructions; hard delete incl. embeddings; JSON export |
| 13 | No limits on proactive suggestions | Predictive help turns into notification spam | Max 1 suggestion a day, quiet hours, stop a suggestion type after 3 dismissals |
| 14 | No quality targets, cost, cold start or language plan | No way to prove memory works; empty memory on day one; Roman Urdu users missed | Eval set with targets; cost per user; 3 onboarding questions; Roman Urdu in tests |


## 3. Architecture: four layers

```text
Chat/Voice -> Turn Router -> [Reminder Engine | Memory Engine | Context Builder] -> Reasoning -> Action
                                   Memory + Context read/write Postgres + pgvector
```

| Layer | Answers | What it is in 8A |
| --- | --- | --- |
| Memory | What do I know about this user? | memories, people and chat history in Postgres + pgvector |
| Context | What matters right now? | A function that assembles time, timezone, upcoming reminders and relevant memories. Nothing stored |
| Reasoning | What should I do? | Rules first, then one LLM call; answers only from what it was given |
| Action | Do it | Existing scheduler + FCM; suggestions follow the autonomy levels in section 8 |

Everything lives in the existing FastAPI backend as modules (ai_service/router, memory, context, reply) with APScheduler for background jobs. The current three-layer reminder parser stays; the router sits in front of it.


## 4. What Speakardo remembers

| Kind | Example | Stored in | Lifecycle | Phase |
| --- | --- | --- | --- | --- |
| Facts | "My office is in Blue Area" | memories | Until changed (versioned) | 8.1 |
| Preferences | "Don't remind me before 8 AM" | memories | Until changed | 8.1 |
| Chat history (episodes) | "I went to the gym yesterday" | conversation_messages | Retention setting, 90 days default | 8.0 |
| Reminder events | created, fired, snoozed, done | reminder_events | Raw log, aggregated later | Log 8.0, use 8B |
| People and relationships | "Sara is my sister" | people (+ aliases) | Until changed | 8.3 |
| Important dates | "Ammi's birthday is June 10" | memories + people | Permanent, yearly | 8.3 |
| Temporary context | "I'm in Lahore this week" | memories (valid_until) | Expires automatically | 8.4 |
| Habits | Gym Mon/Wed/Fri around 6 PM | habits | candidate, confirmed, active, decaying, archived | 8B |
| Places | Home, Work (user-defined) | places | Until changed | Places module |
| Calendar | "Presentation Tue 10 AM" | Read live, not copied | Not stored | Calendar module |


## 5. Rules every memory follows

| Attribute | Rule |
| --- | --- |
| Source | user_explicit, conversation, reminder, onboarding, manual_edit, behavior, calendar. Shown to the user: "You told me on Sep 12". |
| Confidence | 1.0 stated; 0.8 clearly implied; at most 0.6 inferred; habits computed. Below 0.5 is never used in answers, only to ask a question. |
| Importance | 0 to 1. Birthdays and doctors high, favourite coffee low. Feeds ranking. |
| Sensitivity | normal, private, sensitive. Sensitive = health, finance, religion, sexuality, political views, exact addresses. |
| Lifespan | temporary (with valid_until), long-term, permanent. |
| Versioning | Same key and person: the old version is superseded and kept in history, never silently overwritten. |
| Audit | Every create, update, use and delete is logged in memory_events. Memory content never goes into application logs. |


## 6. From message to memory

1. Store the message in chat history.
2. **Rules first**: "remember that...", "forget...", "what do you know about me", "when is X's birthday", plus existing reminder patterns. No LLM cost.
3. **Otherwise one LLM call** returns intent, reminder details, memory candidates and people or dates mentioned, as strict JSON.
4. The **save policy** below decides each candidate.
5. Act: create the reminder, answer from memory, or reply.
6. Return the reply with memory chips: "Saved · Undo", "Updated", "Used: Sara's birthday".

| Situation | What Speakardo does |
| --- | --- |
| Explicit request, or a clearly stated lasting fact (not sensitive) | Saves it and shows "Saved · Undo" |
| Same key as an existing memory ("I moved to Lahore") | Updates it, keeps the old version, shows "Updated (was Islamabad)" |
| Temporary fact ("in Karachi this week") | Saves with an end date |
| Sensitive and stated ("I'm diabetic") | Asks first; saves only with opt-in, encrypted, no embedding |
| Sensitive and only implied ("pick up Mom's medicine") | Never saves a health fact; keeps only the reminder |
| A guess or unclear statement | Doesn't save |
| "Remember that you must always..." | Never treated as an instruction |
| Learning paused | Saves nothing |


## 7. Finding the right memory

1. **Exact lookup**: a known person or alias plus a key ("Sara's birthday") is answered with plain SQL.
2. **Search by meaning**: pgvector returns the top 20 active, currently valid memories, filtered by person or category.
3. **Always-on profile**: about 150 tokens of high-importance basics in every call.

> **score = 0.55 × similarity + 0.20 × importance + 0.15 × confidence + 0.10 × recency**

Budget: 8 to 12 memories, about 800 tokens per call. Speakardo answers only from the memories and reminders it was given; if nothing matches it says "I don't have that saved. Want to tell me?" Questions such as "When is my dentist appointment?" search reminders too.


## 8. Autonomy and proactive help

| Level | Behaviour | When allowed |
| --- | --- | --- |
| 0 Observe | Learns quietly | Whenever learning is on |
| 1 Suggest | "You usually go to the gym at 6 PM. Want a reminder?" | From 8B, confirmed habits only |
| 2 Create with confirmation | "Make this a weekly reminder?" | Once Level 1 suggestions are accepted often |
| 3 Act automatically | Creates or moves reminders itself | Only per type, with explicit opt-in; never for important reminders |

**Guardrails:** at most one proactive suggestion a day, quiet hours respected, a suggestion type stops after three dismissals, and existing reminders are never changed without permission.


## 9. Privacy and trust

**User controls**, in chat and in the Memory screen: view, see why (source and date), edit, forget one, forget a category ("forget everything about my health"), forget everything, pause learning (chat, behaviour and location separately), and export as JSON.

- **Provider allowlist:** calls containing memories or chat history go only to AI providers whose API terms say they don't train on or keep the data.
- **Sensitive memories:** opt-in, explicit only, encrypted in the application, no embeddings, never in the always-on profile.
- **Real deletion:** within 24 hours, including embeddings and old versions. Deleting the account removes all memory data.
- **Honest labels:** the Memory screen says "Private and encrypted" only once encryption and the allowlist are live.


## 10. Roadmap

| Milestone | Delivers | Research stage |
| --- | --- | --- |
| 8.0 Foundations | Postgres + pgvector, stored chat history, reminder_events log, embeddings, provider allowlist | MVP groundwork |
| 8.1 Talk and remember | Turn router, save, recall and forget in chat, memory chips, first 100 test cases | MVP |
| 8.2 Memory screen and privacy | Real Memory screen, edit, delete, export, toggles, encryption | V1 |
| 8.3 People and dates | People with aliases, birthdays turned into reminders, onboarding questions | V1 |
| 8.4 Background learning | Background extraction, versioning, expiry, merging duplicates | V1 |
| 8B Habits | Habit mining, Patterns screen, Level 1 suggestions, better reminder times | V1 to V2 |
| Calendar module | Calendar-aware reminders ("prepare Monday evening for Tuesday's presentation") | V2 |
| Places module | User-defined places, leave and arrive reminders | V2 |
| Predictive assistant | Predictive reminders, travel buffers, personal knowledge graph | V3 |

Ship 8.1 to 10 to 20 real users before polishing 8.2. The first question to answer is whether people tell Speakardo things and come back for them.


## 11. How we know it works

| Quality check | Target |
| --- | --- |
| Saved memories that are correct (precision) | 95% or higher |
| Stated facts that get saved (recall) | 80% or higher |
| Sensitive memories saved without consent | 0 |
| Correct memory in the top 5 results | 90% or higher |
| Answers that invent a memory | 0 |
| Extra response time from memory (median) | Under 400 ms |

**Business metrics:** share of weekly users with 5 or more memories; share of replies that use a memory; undo rate on automatic saves (under 5%); suggestion acceptance rate (from 8B); and, most important, **30-day retention of users with 5+ memories compared with users with none**. That number is the proof that memory is the moat.


## 12. Open decisions

| Decision | Recommendation |
| --- | --- |
| Free vs Pro | Core memory free and unlimited (it drives retention). Habits, predictive suggestions and calendar context in Pro. |
| AI providers allowed to see memories | **Decided:** Anthropic and OpenAI APIs only (`MEMORY_SAFE_PROVIDERS`); other providers for memory-free reminder parsing. |
| Chat history retention | **Decided:** 90 days by default, with 30 days, 1 year or forever as options. |
| Health memories in 8A | **Decided:** not in 8.1; they arrive in 8.2 with encryption and an opt-in toggle. |
| People table timing | Keep in 8A (recommended). |
| Roman Urdu | **Decided:** a separate language milestone after 8.3; Module 8 ships English-only. |
