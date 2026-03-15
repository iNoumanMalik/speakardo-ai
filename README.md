# AI Reminder App

An intelligent **chat-based reminder application** that allows users to create reminders using natural language instead of manual forms.

Users simply type or speak messages like:

```
Remind me to take medicine at 11 PM
Wake me up tomorrow at 7
Call Ali at 5pm
```

The system uses AI to extract the task and time automatically and schedules reminders.

The goal of this project is to explore whether **conversational reminder creation** can replace traditional reminder apps.

---

# Features (MVP)

### Chat-Based Reminder Creation

Users interact with the app through a chat interface similar to messaging apps.

Example:

```
User: Remind me to call mom tomorrow at 8
AI: Got it! I'll remind you to call mom tomorrow at 8 AM.
```

---

### AI Reminder Parsing

Natural language messages are converted into structured reminder data.

Example output:

```
{
  "task": "call mom",
  "datetime": "2026-03-15T08:00:00",
  "repeat": null
}
```

---

### Reminder List

Users can view all scheduled reminders.

```
Today
• Take medicine – 11:00

Tomorrow
• Gym – 6:00
```

Users can:

* mark reminders complete
* delete reminders

---

### Push Notifications

When the scheduled time arrives, the user receives a notification.

Example:

```
Reminder
Take medicine
```

---

### Voice Input

Users can create reminders using voice input.

Speech is converted to text and processed by the AI reminder parser.

---

# Tech Stack

### Mobile App

* Flutter

### Backend API

* Python
* FastAPI

### Database

* PostgreSQL

### AI Processing

* LLM-based natural language parsing

### Notifications

* Firebase Cloud Messaging

---

# Project Structure

```
ai-reminder-app
│
├── mobile_app/        # Flutter application
├── backend/           # FastAPI backend
├── ai_service/        # AI reminder extraction logic
├── database/          # Database schema and migrations
├── docs/              # Project documentation
├── scripts/           # Development scripts
├── docker/            # Docker setup
└── README.md
```

---

# System Architecture

```
User Message
     │
     ▼
Flutter Chat Interface
     │
     ▼
Backend API (FastAPI)
     │
     ▼
AI Reminder Parser
     │
     ▼
Structured Reminder Data
     │
     ▼
PostgreSQL Database
     │
     ▼
Reminder Scheduler
     │
     ▼
Push Notification
```

---

# Getting Started

## 1. Clone the Repository

```
git clone https://github.com/yourusername/ai-reminder-app.git
cd ai-reminder-app
```

---

# Backend Setup

Navigate to backend folder:

```
cd backend
```

Create virtual environment:

```
python -m venv venv
```

Activate environment:

Mac / Linux

```
source venv/bin/activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Run server:

```
uvicorn app.main:app --reload
```

Backend will run on:

```
http://localhost:8000
```

---

# Mobile App Setup

Navigate to Flutter project:

```
cd mobile_app
```

Install dependencies:

```
flutter pub get
```

Run application:

```
flutter run
```

---

# Future Improvements

Possible features after MVP validation:

* Smart reminders based on behavior
* Location-based reminders
* AI assistant conversation
* Calendar integration
* Habit tracking
* AI reminder phone calls
* Multi-device synchronization

---

# Contribution

Contributions are welcome.

If you want to improve the project:

1. Fork the repository
2. Create a new branch
3. Submit a pull request

---

# Vision

The long-term goal is to build a **conversational AI life assistant** that helps users manage their tasks, habits, and daily life through natural conversation.

---
