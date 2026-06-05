from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from models.models import db, GenerationSession, TimetableEntry, Course
from services.llm_service import LLMTimetableService

generate_bp = Blueprint("generate", __name__)


@generate_bp.route("/generate", methods=["GET"])
@login_required
def generate_page():
    sessions = GenerationSession.query.order_by(GenerationSession.created_at.desc()).limit(8).all()
    # Get distinct departments and levels from the course table
    courses = Course.query.all()
    departments = sorted(set(c.department for c in courses))
    levels = sorted(set(c.level for c in courses))
    return render_template("generate.html", sessions=sessions,
                           departments=departments, levels=levels)


@generate_bp.route("/generate/start", methods=["POST"])
@login_required
def start_generation():
    semester = request.form.get("semester", "ALPHA")
    department = request.form.get("department", "ALL")
    level_filter = request.form.get("level_filter", "ALL")

    gs = GenerationSession(
        semester=semester,
        department=department,
        level_filter=level_filter,
        status="PENDING",
    )
    db.session.add(gs)
    db.session.commit()
    session_id = gs.id

    LLMTimetableService().generate_timetable(session_id)
    return jsonify({"success": True, "session_id": session_id})


@generate_bp.route("/generate/course-count")
@login_required
def course_count():
    dept = request.args.get("dept", "ALL")
    level = request.args.get("level", "ALL")
    q = Course.query
    if dept and dept != "ALL":
        q = q.filter_by(department=dept)
    if level and level != "ALL":
        try:
            q = q.filter_by(level=int(level))
        except ValueError:
            pass
    return jsonify({"count": q.count()})


@generate_bp.route("/generate/status/<int:session_id>")
@login_required
def generation_status(session_id):
    gs = GenerationSession.query.get_or_404(session_id)
    return jsonify({
        "status": gs.status,
        "iteration_count": gs.iteration_count,
        "hard_violations": gs.hard_violations,
        "soft_violations": gs.soft_violations,
        "total_time": round(gs.total_time_seconds, 2),
        "log_output": gs.log_output or "",
    })
