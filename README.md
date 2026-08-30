# 🤖 AI Teacher Bot

Telegram ပေါ်မှာ မြန်မာ လူငယ်တွေကို Programming နဲ့ Technology သင်ပေးတဲ့ AI Teacher Agent။

## ✨ Features

- 📚 နေ့စဉ် အလိုအလျောက် သင်ခန်းစာ (မနက် + ည)
- 🤖 Cloudflare Workers AI နဲ့ Lesson ထုတ်တယ်
- 📢 Approved Groups တွေကို Auto-Share
- 👑 Owner Commands (၄၀+)
- 🔗 Link Scanner — Group တွေထဲက Public Links ရှာတယ်
- 📝 Teacher Agent — AI က Proposal တင်ပြီး Owner ခွင့်ပြုမှ ပြောင်းလဲနိုင်
- 🎓 Student Project System — လကုန် Project Challenge + Submission
- 🛡️ Safety Controls — Emergency Stop, Rate Limiting
- 🚀 Universal Deploy Script — VPS နဲ့ Cloud PaaS နှစ်မျိုးလုံး

## 📁 Project Structure

# 🤖 AI Teacher Bot

An AI-powered Telegram Teacher Agent that teaches Programming and Technology to Myanmar youth — completely free.

## ✨ Features

- 📚 Automated daily lessons (Morning + Evening)
- 🤖 AI content generation via Cloudflare Workers AI
- 📢 Auto-share to approved Telegram groups
- 👑 40+ Owner commands for full control
- 🔗 Link scanner — discovers public group links from messages
- 📝 Teacher Agent — AI proposes changes, Owner approves
- 🎓 Student Project System — monthly challenges & submissions
- 🛡️ Safety controls — emergency stop, rate limiting
- 🚀 Universal deployment script — works on VPS & Cloud PaaS

## 📁 Project Structure

```

ai_teacher_bot/
├── main.py                  # Entry point
├── config.py                # Configuration
├── database.py              # Database layer
├── utils.py                 # Utilities
├── deploy.sh                # Deployment script
├── requirements.txt         # Python dependencies
├── .env.example             # Environment sample
│
├── modules/
│   ├── ai_generator.py      # AI content generation
│   ├── telegram_client.py   # Telegram API client
│   ├── publisher.py         # Publishing workflow
│   ├── curriculum.py        # Curriculum management
│   ├── scheduler.py         # Auto post scheduling
│   ├── group_manager.py     # Group CRUD operations
│   ├── share_distributor.py # Auto-share logic
│   ├── owner.py             # Owner commands
│   ├── owner_extra.py       # Extra Owner commands
│   ├── teacher_agent.py     # AI Teacher Agent
│   ├── student_system.py    # Student project system
│   ├── safety.py            # Safety controls
│   └── bot_runner.py        # Bot polling loop
│
├── scripts/
│   ├── run_migrations.py    # DB migration runner
│   ├── test_bot.py          # Test suite
│   └── health_check.py      # Health check
│
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_add_group_sharing.sql
│   ├── 003_add_app_state.sql
│   ├── 004_add_found_links.sql
│   ├── 005_add_agent_tables.sql
│   └── 006_add_student_system.sql
│
├── data/
│   └── python_curriculum.json
│
└── logs/
└── app.log

```

## 🚀 Quick Start

### 1. Clone the Project

```bash
git clone https://github.com/your_username/ai-teacher-bot.git
cd ai-teacher-bot
```

2. Environment Setup

```bash
cp .env.example .env
nano .env  # Fill in your credentials
```

3. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. Run Migrations

```bash
python scripts/run_migrations.py
```

5. Run Tests

```bash
python scripts/test_bot.py
```

6. Start the Bot

```bash
python main.py
```

🖥️ VPS Deployment

```bash
chmod +x deploy.sh
bash deploy.sh
```

The script automatically:

· Detects VPS vs Cloud PaaS environment
· Creates virtual environment
· Installs dependencies
· Runs database migrations
· Configures systemd service (if root)
· Starts the bot

👑 Owner Commands

Category Commands
Basic /status, /pause, /resume
Groups /groups, /grouplist, /approve, /remove
Posting /global, /broadcast, /post, /share, /editpost, /deletepost
Links /scan, /join, /joinall, /reject, /clearlinks
Moderation /ban, /unban, /kick, /pin, /unpin
Schedule /settime, /setmonth, /scheduled, /skipday, /resetday
Stats /stats, /lessonstatus, /agentstatus, /uptime
Maintenance /backup, /clearlogs, /restart
AI Agent /proposals, /approveproposal, /rejectproposal, /analyze, /plannext, /agentlogs
Student /createchallenge, /submissions, /review, /projectstats

🤖 Teacher Agent

The AI Teacher Agent can:

· Analyze current month progress
· Plan next month curriculum
· Generate proposals for Owner review
· Learn from student feedback

Important: The Agent has NO authority to make changes directly. All changes require Owner approval.

🔒 Safety

· Owner Only — Non-owner messages are completely ignored
· Emergency Stop — Instantly halt all operations
· Rate Limiting — Prevents API abuse
· Duplicate Prevention — Lessons are never posted twice
· No Auto-Join — Groups require Owner approval before joining

📊 Tech Stack

· Language: Python 3.8+
· AI: Cloudflare Workers AI
· Database: SQLite (dev) / Cloudflare D1 (prod)
· Platform: Telegram Bot API
· Scheduler: APScheduler

📄 License

MIT License

🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change
