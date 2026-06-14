import os
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

load_dotenv()

from models.models import db, Admin, Constraint, GenerationSession, TimetableEntry, Course, Room, Lecturer, StudentGroup
from routes.auth import auth_bp, bcrypt
from routes.upload import upload_bp
from routes.constraints import constraints_bp
from routes.generate import generate_bp
from routes.export import export_bp

app = Flask(__name__)
app.config.from_object("config.Config")

db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(constraints_bp)
app.register_blueprint(generate_bp)
app.register_blueprint(export_bp)


@app.route("/")
def index():
    return redirect(url_for("main.dashboard"))


from flask import Blueprint
main_bp = Blueprint("main", __name__)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "courses": Course.query.count(),
        "rooms": Room.query.count(),
        "lecturers": Lecturer.query.count(),
        "schedules": GenerationSession.query.count(),
    }
    recent_sessions = GenerationSession.query.order_by(GenerationSession.created_at.desc()).limit(5).all()
    hard_cons = Constraint.query.filter_by(constraint_type="HARD", is_active=True).count()
    soft_cons = Constraint.query.filter_by(constraint_type="SOFT", is_active=True).count()
    last_session = GenerationSession.query.order_by(GenerationSession.created_at.desc()).first()
    return render_template("dashboard.html", stats=stats, recent_sessions=recent_sessions,
                           hard_cons=hard_cons, soft_cons=soft_cons, last_session=last_session)


app.register_blueprint(main_bp)


@main_bp.route("/admin/reset-db")
@login_required
def reset_db():
    """Drop and recreate all tables — use once after a schema change on Vercel."""
    try:
        db.drop_all()
        db.create_all()
        seed_database()
        return (
            "<html><body style='font-family:sans-serif;padding:40px;text-align:center;'>"
            "<h2 style='color:#2E7D32;'>&#10003; Database Reset Successful</h2>"
            "<p>All tables dropped and recreated with the latest schema.<br>"
            "Default admin (<b>admin@timetai.ng</b>) and constraints reloaded.</p>"
            "<a href='/dashboard' style='color:#1A3C5E;font-weight:600;'>Go to Dashboard &rarr;</a>"
            "</body></html>"
        )
    except Exception as ex:
        return (
            f"<html><body style='font-family:sans-serif;padding:40px;text-align:center;'>"
            f"<h2 style='color:#c62828;'>&#10007; Reset Failed</h2>"
            f"<pre style='text-align:left;background:#fafafa;padding:16px;border-radius:8px;'>{ex}</pre>"
            f"<a href='/dashboard' style='color:#1A3C5E;font-weight:600;'>Go to Dashboard &rarr;</a>"
            f"</body></html>"
        )


def _init_db():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()
    seed_database()


DEFAULT_HARD_CONSTRAINTS = [
    {"category": "room", "description": "No room may be assigned to more than one course at the same day and time slot"},
    {"category": "lecturer", "description": "No lecturer may be scheduled for two or more courses simultaneously"},
    {"category": "capacity", "description": "The number of students in a group must not exceed the room capacity"},
    {"category": "group", "description": "No student group may have two or more lectures at the same time"},
    {"category": "lab", "description": "Laboratory courses must only be assigned to rooms of type LAB"},
    {"category": "availability", "description": "Lecturers must only be scheduled during their declared available time slots"},
]

DEFAULT_SOFT_CONSTRAINTS = [
    {"category": "time", "description": "Avoid scheduling courses before 8:00 AM or after 5:00 PM"},
    {"category": "preference", "description": "Respect lecturer time preferences where possible"},
    {"category": "balance", "description": "Minimise idle time gaps for student groups between consecutive lectures"},
    {"category": "distribution", "description": "Spread lectures evenly across the week rather than clustering them"},
    {"category": "level", "description": "Avoid scheduling the same student group for more than 3 consecutive hours"},
]


def seed_database():
    if Admin.query.count() == 0:
        from flask_bcrypt import generate_password_hash
        admin = Admin(
            email="admin@timetai.ng",
            password_hash=generate_password_hash("Admin@TimetAI2025").decode("utf-8"),
        )
        db.session.add(admin)
        db.session.commit()
        print("[SEED] Admin account created: admin@timetai.ng")

    if Constraint.query.count() == 0:
        for c in DEFAULT_HARD_CONSTRAINTS:
            db.session.add(Constraint(constraint_type="HARD", category=c["category"], description=c["description"]))
        for c in DEFAULT_SOFT_CONSTRAINTS:
            db.session.add(Constraint(constraint_type="SOFT", category=c["category"], description=c["description"]))
        db.session.commit()
        print("[SEED] Default constraints loaded.")


_startup_error = None

with app.app_context():
    try:
        _init_db()
    except Exception as _e:
        _startup_error = str(_e)
        print(f"[STARTUP] DB init failed: {_e}", flush=True)


@app.route("/health")
def health():
    """Public health-check — shows DB connection status and any startup error."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
        db_msg = "Connected"
    except Exception as ex:
        db_ok = False
        db_msg = str(ex)
    status = "ok" if (db_ok and not _startup_error) else "error"
    from flask import jsonify as _j
    return _j({
        "status": status,
        "db": db_ok,
        "db_msg": db_msg,
        "startup_error": _startup_error,
    }), (200 if status == "ok" else 500)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
