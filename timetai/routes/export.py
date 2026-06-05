from flask import Blueprint, render_template, make_response, send_file, flash, redirect, url_for
from flask_login import login_required
from models.models import TimetableEntry, GenerationSession
from services.exporter import export_csv, export_excel, export_pdf

export_bp = Blueprint("export", __name__)


@export_bp.route("/timetable")
@login_required
def timetable_page():
    entries = TimetableEntry.query.all()
    data = [e.to_dict() for e in entries]
    levels = sorted(set(e["level"] for e in data if e.get("level")))
    last_session = GenerationSession.query.order_by(GenerationSession.created_at.desc()).first()
    return render_template("timetable.html", entries=data, levels=levels, last_session=last_session)


@export_bp.route("/conflicts")
@login_required
def conflicts_page():
    from services.validator import ConstraintValidator
    from models.models import Constraint
    entries = [e.to_dict() for e in TimetableEntry.query.all()]
    constraints = [c.to_dict() for c in Constraint.query.filter_by(is_active=True).all()]
    validator = ConstraintValidator()
    result = validator.validate(entries, constraints)
    last_session = GenerationSession.query.order_by(GenerationSession.created_at.desc()).first()
    return render_template("conflicts.html", result=result, last_session=last_session)


@export_bp.route("/export")
@login_required
def export_page():
    from services.validator import ConstraintValidator
    from models.models import Constraint
    entries = [e.to_dict() for e in TimetableEntry.query.all()]
    constraints = [c.to_dict() for c in Constraint.query.filter_by(is_active=True).all()]
    validator = ConstraintValidator()
    result = validator.validate(entries, constraints)
    last_session = GenerationSession.query.order_by(GenerationSession.created_at.desc()).first()
    return render_template("export.html", result=result, entries=entries, last_session=last_session)


@export_bp.route("/export/csv")
@login_required
def download_csv():
    csv_data = export_csv()
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=timetable.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@export_bp.route("/export/excel")
@login_required
def download_excel():
    output = export_excel()
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="timetable.xlsx",
    )


@export_bp.route("/export/pdf")
@login_required
def download_pdf():
    output = export_pdf()
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="timetable.pdf",
    )
