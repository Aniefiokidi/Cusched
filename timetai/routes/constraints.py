from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.models import db, Constraint
from services.validator import ConstraintValidator

constraints_bp = Blueprint("constraints", __name__)


@constraints_bp.route("/constraints", methods=["GET"])
@login_required
def constraints_page():
    hard = Constraint.query.filter_by(constraint_type="HARD").order_by(Constraint.id).all()
    soft = Constraint.query.filter_by(constraint_type="SOFT").order_by(Constraint.id).all()
    return render_template("constraints.html", hard_constraints=hard, soft_constraints=soft)


@constraints_bp.route("/constraints/add", methods=["POST"])
@login_required
def add_constraint():
    ctype = request.form.get("constraint_type", "SOFT").upper()
    category = request.form.get("category", "general").strip()
    description = request.form.get("description", "").strip()
    if not description:
        flash("Description is required.", "error")
        return redirect(url_for("constraints.constraints_page"))
    c = Constraint(constraint_type=ctype, category=category, description=description)
    db.session.add(c)
    db.session.commit()
    flash("Constraint added successfully.", "success")
    return redirect(url_for("constraints.constraints_page"))


@constraints_bp.route("/constraints/toggle/<int:cid>", methods=["POST"])
@login_required
def toggle_constraint(cid):
    c = Constraint.query.get_or_404(cid)
    c.is_active = not c.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": c.is_active})


@constraints_bp.route("/constraints/delete/<int:cid>", methods=["POST"])
@login_required
def delete_constraint(cid):
    c = Constraint.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"success": True})


@constraints_bp.route("/constraints/parse-nl", methods=["POST"])
@login_required
def parse_nl():
    data = request.get_json()
    nl_text = (data or {}).get("text", "").strip()
    if not nl_text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    validator = ConstraintValidator()
    parsed = validator.parse_natural_language_constraint(nl_text)
    c = Constraint(
        constraint_type=parsed.get("type", "SOFT").upper(),
        category=parsed.get("category", "general"),
        description=nl_text,
        is_natural_language=True,
    )
    c.parsed_rule = parsed
    db.session.add(c)
    db.session.commit()
    return jsonify({"success": True, "constraint": c.to_dict(), "parsed": parsed})
