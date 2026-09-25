# **Speakardo Software Requirements Specification** 

# **(SRS)** 

Version: 1.1 

Product: Speakardo 

Category: AI Life Assistant 

Status: Living Technical Document 

## Revision History

| Version | Date | Changes |
| --- | --- | --- |
| 1.0 | 2026-06 | Initial SRS |
| 1.1 | 2026-09-25 | Module 2 expanded into a conversational assistant; Module 8 (AI Memory) fully specified with a separate design doc; Memories data model and Memory API expanded; roadmap order changed (Memory before Shared Reminders and Teams) |

Detailed design for Module 8: `docs/Project/Speakardo Module 8 - AI Memory System Design.md` 

# **1. Introduction** 

## **1.1 Purpose** 

This document defines the technical and functional requirements for Speakardo, an AI-powered life assistant that enables users to create reminders, manage personal memory, receive notifications, and eventually automate parts of their daily life through natural conversation. 

This SRS serves as the source of truth for engineering, design, AI systems, infrastructure, and future product expansion. 

# **2. Product Scope** 

Speakardo is not a traditional reminder application. 

Speakardo is an AI Life Assistant that: 

- Understands natural language 

- Creates reminders automatically 

- Learns user behavior 

- Maintains personal memory 

- Delivers reminders through multiple channels 

- Supports collaborative reminders 

- Evolves toward autonomous assistance 

1 

# **3. User Roles** 

## **3.1 Guest** 

Capabilities: 

- Landing page access • Signup • Login 

Restrictions: 

- Cannot create reminders • Cannot access assistant 

## **3.2 User** 

Capabilities: 

- Chat with AI 

- Create reminders 

- Manage reminders • Voice interaction • Receive notifications • Manage profile • Invite others 

## **3.3 Team Member** 

Capabilities: 

- Receive shared reminders • Collaborate on reminders • Participate in shared workspaces 

## **3.4 Family Member** 

Capabilities: 

- Receive family reminders 

- Share household reminders 

2 

## **3.5 Admin** 

Capabilities: 

- User management 

- System monitoring 

- Abuse prevention 

- Analytics access 

# **4. Functional Requirements** 

# **Module 1: Authentication** 

## **Features** 

- Email signup 

- Email login 

- Password reset 

- Social login 

- Google login 

- Apple login 

- Session management 

- JWT authentication 

- Refresh tokens 

### **Acceptance Criteria** 

User can: 

- Register account 

- Login securely 

- Logout securely 

- Recover account 

3 

# **Module 2: AI Chat Assistant** 

## **Features** 

### **Natural Language Reminder Creation** 

Examples: 

"Remind me to call Ali tomorrow at 5" 

"Wake me at 7 AM" 

"Pay electricity bill every month" 

### **AI Responsibilities** 

Extract: 

- Task • Date • Time • Recurrence • Priority 

Generate confirmation: 

"Got it. I'll remind you tomorrow at 5 PM." 

## **AI Parsing Pipeline** 

### **Level 1** 

Rule-based extraction 

Tools: 

- Regex • DateParser 

- Duckling 

### **Level 2** 

AI fallback 

4 

Providers: 

- OpenAI • Gemini 

- Claude 

Used when confidence is low. 

## **Conversational Assistant (added in v1.1)** 

Chat is not only a reminder parser. Every message goes through a Turn Router that classifies intent: 

- reminder_create / reminder_edit 
- memory_save / memory_query / memory_forget / memory_list 
- chat (general conversation) 

Requirements: 

- Rules first; otherwise one combined LLM call returns intent, reminder slots and memory candidates as strict JSON. 
- Chat messages are stored server-side (`conversation_messages`) with user-controlled retention (default 90 days). 
- The app loads history via GET /chat/history. 
- Replies use relevant memories; the assistant says "I don't have that saved" instead of guessing. 
- The greeting is personal (uses the user's name when known), not "AI Reminder assistant". 
- Input in English, Roman Urdu and Urdu is supported. 

# **Module 3: Reminder Management** 

## **Reminder Types** 

### **One-Time Reminder** 

Example: 

Call Mom at 5 PM 

### **Recurring Reminder** 

Examples: 

Every day 

Every week 

Every month 

Custom schedules 

### **Location Reminder** 

Examples: 

Remind me when I reach office 

Remind me when I leave home 

### **Context Reminder** 

Examples: 

5 

Remind me after my meeting 

Remind me before my flight 

### **Smart Reminder** 

AI determines optimal time. 

## **Reminder Actions** 

Create 

Update 

Delete 

Archive 

Complete 

Snooze 

Reschedule 

Duplicate 

Share 

# **Module 4: Notifications** 

## **Notification Channels** 

### **Push Notification** 

Android 

iOS 

Web 

6 

### **Voice Notification** 

TTS reminder playback 

### **Email Notification** 

Optional 

### **SMS Notification** 

Premium feature 

### **AI Call Reminder** 

Premium feature 

Example: 

"Hello Nouman. 

This is your reminder. 

Take your medicine." 

Features: 

- Human-like AI voice 

- Personalized voice 

- Multiple languages 

- Retry if unanswered 

# **Module 5: Shared Reminders** 

## **Shared Reminder System** 

Users can assign reminders to others. 

Example: 

Manager → Employee 

7 

Parent → Child 

Husband → Wife 

Friend → Friend 

### **Shared Reminder States** 

Pending 

Accepted 

Declined 

Completed Expired 

### **Features** 

Assign reminder 

Transfer reminder 

Track completion 

Send follow-ups 

View history 

# **Module 6: Team Workspaces** 

## **Workspace Features** 

Create team 

Invite members 

Assign reminders 

Shared schedules 

8 

Shared tasks 

Shared notifications 

Team analytics 

## **Roles** 

Owner 

Admin 

Member 

Viewer 

# **Module 7: Voice Assistant** 

## **Features** 

Voice Input 

Speech-to-text 

Voice Commands 

Hands-free usage 

Wake words 

Future: 

"Hey Speakardo" 

## **Supported Languages** 

English 

Urdu 

9 

Arabic 

Hindi 

Future multilingual support 

# **Module 8: AI Memory System** 

Full design: `docs/Project/Speakardo Module 8 - AI Memory System Design.md` 

## **Goal** 

Speakardo remembers what users tell it, answers questions from that memory, and uses it to set better reminders, while the user can always see, edit and delete what is kept. 

Product promise: "Don't tell Speakardo when. Tell Speakardo what matters." 

## **Memory Kinds** 

- fact: "My office is in Blue Area" 
- preference: "Don't remind me before 8 AM" 
- important_date: "My mother's birthday is June 10" 
- relationship: "Sara is my sister" (linked to a People record with aliases, e.g. Mom / Ammi / my mother) 
- note: personal notes 
- event: life events ("I moved to Lahore") 
- habit: learned from app activity (Module 8B, separate table) 

## **Every Memory Has** 

Source, confidence, importance, sensitivity (normal / private / sensitive), status, validity dates (for temporary facts), and version history. 

## **Save Policy** 

- Explicit request or clearly stated lasting fact (not sensitive): save immediately, show "Saved · Undo" in chat. 
- Same key as an existing memory: replace it, keep the old one in history, show "Updated". 
- Temporary fact: save with an end date. 
- Sensitive fact stated explicitly: ask first; save only with opt-in; encrypted; no embedding. 
- Sensitive fact only implied: never save. 
- Unclear or guessed: do not save. 
- Instructions disguised as memories are never followed. 

## **Memory Retrieval** 

- Exact lookup first (person/alias + key), then semantic search (pgvector), plus an always-included profile. 
- Ranking: score = 0.55 similarity + 0.20 importance + 0.15 confidence + 0.10 recency (recency fixed at 1.0 for lasting facts). 
- Budget: 8 to 12 memories, about 800 tokens per call. 
- Questions search memories and reminders together. 

### **Examples** 

"My mother's birthday is June 10." → saved + offer yearly reminder 

"I prefer meetings after 10 AM." → saved as preference 

"What did I tell you about my mother?" → answered from memory 

"When is my next dentist appointment?" → answered from reminders 

"Remind me to call Ammi on her birthday." → resolves person and date from memory 

## **User Controls** 

View, explain source, edit, forget one, forget a category, forget everything, pause learning, export (JSON). Available in chat and in the Memory screen. 

## **Privacy Requirements** 

- LLM calls that include memories or chat history go only to allowlisted providers that do not train on or retain API data. 
- Sensitive memories are encrypted at the application level. 
- Deleted memories are hard-deleted within 24 hours, including embeddings and old versions. 
- Memory content is never written to logs. 

## **Milestones** 

8.0 Foundations → 8.1 Talk and remember → 8.2 Memory screen and privacy → 8.3 People and dates → 8.4 Background learning → 8B Habits 

# **Module 9: Calendar Integration** 

Integrations: 

10 

Google Calendar 

Apple Calendar 

Outlook 

## **Features** 

Sync events 

Conflict detection 

Smart scheduling 

Availability checking 

# **Module 10: AI Scheduling Assistant** 

Examples: 

"Find time next week for a dentist appointment." 

"Move all meetings after 3 PM." 

Capabilities: 

Schedule optimization 

Conflict resolution 

Time blocking 

Priority management 

# **Module 11: Autonomous Assistant** 

Future System 

Capabilities: 

11 

Book appointments 

Send messages 

Reschedule meetings 

Order services 

Manage daily routines 

Take actions with permission 

# **Module 12: Analytics** 

User Analytics 

Completed reminders 

Missed reminders 

Reminder categories 

Behavior trends 

Productivity metrics 

# **5. Database Design** 

## **Users** 

Fields: 

id 

email 

password_hash 

name 

avatar_url 

12 

timezone 

language 

created_at 

updated_at 

## **Devices** 

Fields: 

id 

user_id 

device_token 

platform 

last_seen 

## **Reminders** 

Fields: 

id 

user_id 

title 

description 

datetime_utc 

repeat_rule 

priority 

status 

13 

source 

created_at 

updated_at 

## **ReminderAssignments** 

Fields: 

id 

reminder_id 

sender_id 

receiver_id 

status 

assigned_at 

completed_at 

## **Notifications** 

Fields: 

id 

user_id 

reminder_id 

channel 

status 

sent_at 

opened_at 

14 

## **Memories** 

Fields: 

id, user_id 

kind (fact, preference, important_date, relationship, note, event) 

category (personal, work, people, health, finance, places, routine, other) 

key (normalised slot, e.g. birthday) 

person_id (nullable, FK People) 

content 

value (jsonb) 

source (user_explicit, conversation, reminder, onboarding, manual_edit, behavior) 

source_message_id 

confidence 

importance 

sensitivity (normal, private, sensitive) 

status (active, pending_confirmation, superseded, deleted) 

superseded_by 

valid_from, valid_until 

embedding (vector 1536, null for sensitive) 

use_count, last_used_at 

created_at, updated_at 

## **People** 

Fields: 

id, user_id, display_name, relationship, aliases, notes, created_at 

## **ConversationMessages** 

Fields: 

id, user_id, session_id, role, content, intent, created_at 

## **MemoryEvents** (audit trail) 

Fields: 

id, memory_id, user_id, action, actor, detail, created_at 

## **MemorySettings** 

Fields: 

memory_enabled, learn_from_chat, sensitive_memory_opt_in, chat_retention_days 

## **Teams** 

Fields: 

id 

name 

owner_id 

created_at 

## **TeamMembers** 

Fields: 

id 

team_id 

user_id 

role 

15 

## **AIInteractions** 

Fields: 

id 

user_id 

prompt 

response 

provider 

tokens 

cost 

created_at 

# **6. API Requirements** 

Authentication 

POST /auth/register 

POST /auth/login 

POST /auth/logout 

POST /auth/refresh 

Chat 

POST /chat 

POST /voice 

GET /chat/history 

Reminders 

16 

POST /reminders 

GET /reminders 

GET /reminders/{id} 

PUT /reminders/{id} 

DELETE /reminders/{id} 

Shared Reminders 

POST /shared 

GET /shared 

PUT /shared/{id} 

Teams 

POST /teams 

GET /teams 

POST /teams/invite 

Memory 

GET /memory (filters: kind, category, person_id, q) 

GET /memory/{id} 

POST /memory 

PATCH /memory/{id} 

POST /memory/{id}/confirm 

POST /memory/{id}/reject 

DELETE /memory/{id} 

DELETE /memory?category={category} 

POST /memory/delete-all 

GET /memory/export 

GET /memory/settings 

PATCH /memory/settings 

People 

GET /people 

POST /people 

PATCH /people/{id} 

DELETE /people/{id} 

Devices 

POST /devices/register 

DELETE /devices/{id} 

17 

# **7. Non-Functional Requirements** 

## **Performance** 

Reminder creation: 

< 2 seconds 

AI response: 

< 5 seconds 

Notification latency: 

< 30 seconds 

## **Scalability** 

Support: 

100,000+ users 

1M reminders/day 

Horizontal scaling support 

## **Security** 

JWT authentication 

HTTPS only 

Encrypted passwords 

Rate limiting 

Secret management 

Data isolation 

Audit logs 

18 

## **Reliability** 

99.9% uptime 

Retry mechanisms 

Dead-letter queue support 

Backup system 

# **8. UI/UX Requirements** 

## **Design Principles** 

Futuristic 

Premium 

Immersive 

AI-native 

Memorable 

## **Requirements** 

Unique layouts 

3D elements 

Animated assistant 

Glassmorphism 

Dark mode 

Micro interactions 

Voice-first experience 

19 

Responsive design 

Accessibility support 

# **9. Technical Architecture** 

Frontend 

Flutter 

Backend 

Python 

FastAPI 

Database 

PostgreSQL 

Cache 

Redis 

Queue 

Celery 

AI Providers 

OpenAI 

Gemini 

Claude 

Notifications 

20 

Firebase Cloud Messaging 

Voice 

Whisper 

ElevenLabs 

OpenAI TTS 

Infrastructure 

Docker 

AWS 

Cloud Run 

Render 

Railway 

# **10. MVP Scope** 

Included: 

Authentication 

Chat interface 

Reminder extraction 

Reminder management 

Push notifications 

Voice input 

Basic AI parsing 

Device registration 

21 

PostgreSQL 

FCM integration 

Excluded: 

AI memory 

Team workspaces 

AI calls 

Calendar integrations 

Autonomous actions 

Advanced analytics 

# **11. Future Roadmap** 

Phase 1 

AI Reminder Assistant 

Phase 2 

Voice Assistant 

Phase 3 

Shared Reminders 

Phase 4 

AI Memory 

Phase 5 

22 

Calendar Assistant 

Phase 6 

AI Phone Calls 

Phase 7 

Team Collaboration 

Phase 8 

Autonomous Life Assistant 

Phase 9 

AI Life Operating System 

# **12. Risks & Assumptions** 

## **Risks** 

High AI costs 

Notification delivery failures 

User retention challenges 

Platform restrictions 

Voice infrastructure costs 

Privacy concerns 

## **Assumptions** 

Users prefer natural language over forms 

23 

Users trust AI for reminders 

Push notifications remain effective 

AI accuracy remains high 

Mobile-first experience is preferred 

Future automation demand will increase 

# **North Star Requirement** 

The user should be able to say: 

"Speakardo, handle it." 

And trust that it will. 

24 

