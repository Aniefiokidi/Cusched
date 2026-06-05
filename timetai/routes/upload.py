import csv
import io
import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.models import db, Course, Room, Lecturer, StudentGroup

upload_bp = Blueprint("upload", __name__)

COURSE_COLS = {"course_code", "course_title", "credit_units", "course_type", "department", "level"}
ROOM_COLS = {"room_name", "room_type", "capacity", "building"}
LECTURER_COLS = {"name", "email", "department", "specialisation", "availability"}
GROUP_COLS = {"group_name", "programme", "level", "student_count"}


def parse_availability(raw: str) -> dict:
    avail = {}
    if not raw:
        return avail
    for day_block in raw.split(","):
        day_block = day_block.strip()
        if ":" not in day_block:
            continue
        day, slots_raw = day_block.split(":", 1)
        avail[day.strip()] = [s.strip() for s in slots_raw.split("|")]
    return avail


@upload_bp.route("/upload", methods=["GET"])
@login_required
def upload_page():
    counts = {
        "courses": Course.query.count(),
        "rooms": Room.query.count(),
        "lecturers": Lecturer.query.count(),
        "groups": StudentGroup.query.count(),
    }
    return render_template("upload.html", counts=counts)


@upload_bp.route("/upload/file", methods=["POST"])
@login_required
def upload_file():
    file_type = request.form.get("file_type")
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"success": False, "error": "Only CSV files are accepted"}), 400

    content = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return jsonify({"success": False, "error": "CSV file is empty"}), 400

    cols = set(rows[0].keys())

    try:
        if file_type == "courses":
            missing = COURSE_COLS - cols
            if missing:
                return jsonify({"success": False, "error": f"Missing columns: {missing}"}), 400
            Course.query.delete()
            for row in rows:
                db.session.add(Course(
                    course_code=row["course_code"].strip(),
                    course_title=row["course_title"].strip(),
                    credit_units=int(row["credit_units"]),
                    course_type=row["course_type"].strip().upper(),
                    department=row["department"].strip(),
                    level=int(row["level"]),
                ))

        elif file_type == "rooms":
            missing = ROOM_COLS - cols
            if missing:
                return jsonify({"success": False, "error": f"Missing columns: {missing}"}), 400
            Room.query.delete()
            for row in rows:
                db.session.add(Room(
                    room_name=row["room_name"].strip(),
                    room_type=row["room_type"].strip().upper(),
                    capacity=int(row["capacity"]),
                    building=row.get("building", "").strip(),
                ))

        elif file_type == "lecturers":
            missing = LECTURER_COLS - cols
            if missing:
                return jsonify({"success": False, "error": f"Missing columns: {missing}"}), 400
            Lecturer.query.delete()
            for row in rows:
                lec = Lecturer(
                    name=row["name"].strip(),
                    email=row["email"].strip(),
                    department=row["department"].strip(),
                    specialisation=row.get("specialisation", "").strip(),
                )
                lec.availability = parse_availability(row.get("availability", ""))
                db.session.add(lec)

        elif file_type == "groups":
            missing = GROUP_COLS - cols
            if missing:
                return jsonify({"success": False, "error": f"Missing columns: {missing}"}), 400
            StudentGroup.query.delete()
            for row in rows:
                db.session.add(StudentGroup(
                    group_name=row["group_name"].strip(),
                    programme=row["programme"].strip(),
                    level=int(row["level"]),
                    student_count=int(row["student_count"]),
                ))
        else:
            return jsonify({"success": False, "error": "Unknown file_type"}), 400

        db.session.commit()
        return jsonify({"success": True, "count": len(rows), "file_type": file_type})

    except Exception as ex:
        db.session.rollback()
        return jsonify({"success": False, "error": str(ex)}), 500
