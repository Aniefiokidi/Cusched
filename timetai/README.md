# CovenantSched — Covenant University Timetable Scheduling System

**Final Year Project** — Ajayi Anjolajesu Tinuola (22CH031986)  
Covenant University, Department of Computer and Information Sciences, 2025

---

## Setup Instructions

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
copy .env.example .env
```
Open `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-key-here
```

### 3. Run the application
```bash
python app.py
```

### 4. Open in browser
```
http://127.0.0.1:5000
```

### 5. Login
- **Email:** admin@timetai.ng
- **Password:** Admin@TimetAI2025  *(CovenantSched v1.0)*

### 6. Upload sample data
Go to **Upload Data** and upload all 4 CSV files from `data/sample/`:
- `courses.csv`
- `rooms.csv`
- `lecturers.csv`
- `student_groups.csv`

### 7. Configure constraints
Go to **Constraints** — default hard and soft constraints are pre-loaded.

### 8. Generate timetable
Go to **Generate Timetable**, select semester, click **Start Generation**.

---

## Project Structure

```
timetai/
├── app.py                  # Application entry point + seeding
├── config.py               # Configuration
├── requirements.txt
├── .env.example
├── models/models.py        # SQLAlchemy database models
├── routes/                 # Flask Blueprints
│   ├── auth.py             # Login/logout
│   ├── upload.py           # CSV upload & parsing
│   ├── constraints.py      # Constraint management
│   ├── generate.py         # LLM generation trigger
│   └── export.py           # View, conflict, export
├── services/
│   ├── llm_service.py      # GPT-4o integration + generation loop
│   ├── validator.py        # Constraint validation engine
│   └── exporter.py         # PDF, Excel, CSV export
├── templates/              # Jinja2 HTML templates
├── static/css/style.css    # Design system
├── static/js/main.js       # Frontend interactions
└── data/sample/            # Sample CSV files
```

## Pages / Screenshots

| URL | Description |
|-----|-------------|
| /login | Authentication page |
| /dashboard | Overview, stats, activity feed |
| /upload | CSV file upload with drag-and-drop |
| /constraints | Hard/soft constraint management + NL parser |
| /generate | GPT-4o generation with live terminal log |
| /timetable | Weekly grid + detailed table view |
| /conflicts | Constraint satisfaction report |
| /export | PDF, Excel, CSV download |
