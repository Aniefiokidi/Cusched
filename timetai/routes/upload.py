import csv
import io
import json
import os
import re
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required
from models.models import db, Course, Room, Lecturer, StudentGroup, TimetableEntry

upload_bp = Blueprint("upload", __name__)

COURSE_COLS = {"course_code", "course_title", "credit_units", "course_type", "department", "level"}
ROOM_COLS = {"room_name", "room_type", "capacity", "building"}
LECTURER_COLS = {"name", "email", "department", "specialisation", "availability"}
GROUP_COLS = {"group_name", "programme", "level", "student_count"}
COMBINED_COLS = {"course", "lecturer", "students", "capacity", "level"}


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


def _extract_dept(course_code: str) -> str:
    m = re.match(r'([A-Za-z]+)', course_code.strip())
    return m.group(1).upper() if m else "GENERAL"


def _parse_first_level(level_str: str) -> int:
    nums = re.findall(r'\b(100|200|300|400|500)\b', str(level_str))
    return int(nums[0]) if nums else 100


def _name_to_email(name: str) -> str:
    TITLES = {"dr", "prof", "mr", "mrs", "ms", "engr", "sir"}
    clean = re.sub(r'[^a-zA-Z\s]', '', name).strip().lower()
    parts = [p for p in clean.split() if p not in TITLES]
    if len(parts) >= 2:
        return f"{parts[-1]}.{parts[0]}@university.edu.ng"
    if parts:
        return f"{parts[0]}@university.edu.ng"
    return f"lecturer_{abs(hash(name)) % 100000}@university.edu.ng"


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


@upload_bp.route("/upload/load-sample", methods=["POST"])
@login_required
def load_sample():
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample")

    def read_sample(filename):
        path = os.path.join(sample_dir, filename)
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    try:
        courses_rows   = read_sample("courses.csv")
        rooms_rows     = read_sample("rooms.csv")
        lecturers_rows = read_sample("lecturers.csv")
        groups_rows    = read_sample("student_groups.csv")

        # Clear timetable entries first — PostgreSQL FK constraints require this
        TimetableEntry.query.delete()
        Course.query.delete()
        for row in courses_rows:
            db.session.add(Course(
                course_code=row["course_code"].strip(),
                course_title=row["course_title"].strip(),
                credit_units=int(row["credit_units"]),
                course_type=row["course_type"].strip().upper(),
                department=row["department"].strip(),
                level=int(row["level"]),
            ))

        Room.query.delete()
        for row in rooms_rows:
            db.session.add(Room(
                room_name=row["room_name"].strip(),
                room_type=row["room_type"].strip().upper(),
                capacity=int(row["capacity"]),
                building=row.get("building", "").strip(),
            ))

        Lecturer.query.delete()
        for row in lecturers_rows:
            lec = Lecturer(
                name=row["name"].strip(),
                email=row["email"].strip(),
                department=row["department"].strip(),
                specialisation=row.get("specialisation", "").strip(),
            )
            lec.availability = parse_availability(row.get("availability", ""))
            db.session.add(lec)

        StudentGroup.query.delete()
        for row in groups_rows:
            db.session.add(StudentGroup(
                group_name=row["group_name"].strip(),
                programme=row["programme"].strip(),
                level=int(row["level"]),
                student_count=int(row["student_count"]),
            ))

        db.session.commit()
        return jsonify({
            "success": True,
            "courses": len(courses_rows),
            "rooms": len(rooms_rows),
            "lecturers": len(lecturers_rows),
            "groups": len(groups_rows),
        })

    except Exception as ex:
        db.session.rollback()
        return jsonify({"success": False, "error": str(ex)}), 500


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


@upload_bp.route("/upload/combined", methods=["POST"])
@login_required
def upload_combined():
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

    # Normalize keys to lowercase and strip whitespace
    rows = [{k.strip().lower(): v for k, v in row.items()} for row in rows]
    cols = set(rows[0].keys())

    # Accept 'venue' as alias for 'room'
    if "venue" in cols and "room" not in cols:
        for row in rows:
            row["room"] = row.get("venue", "")
        cols.add("room")

    missing = COMBINED_COLS - cols
    if missing:
        return jsonify({"success": False, "error": f"Missing columns: {missing}"}), 400

    try:
        # ── COURSES (deduplicate by course_code) ──
        seen_courses = {}
        for row in rows:
            code = row["course"].strip()[:100]
            if not code or code in seen_courses:
                continue
            room_name = row.get("room", "").strip()
            c_type = "LAB" if "LAB" in room_name.upper() else "LECTURE"
            seen_courses[code] = Course(
                course_code=code,
                course_title=code,
                credit_units=3,
                course_type=c_type,
                department=_extract_dept(code),
                level=_parse_first_level(row["level"]),
            )

        # ── ROOMS (deduplicate by room_name) ──
        seen_rooms = {}
        for row in rows:
            rname = row.get("room", "").strip()
            if not rname or rname in seen_rooms:
                continue
            r_type = "LAB" if "LAB" in rname.upper() else "LECTURE_HALL"
            try:
                cap = int(float(row["capacity"]))
            except (ValueError, TypeError):
                cap = 0
            seen_rooms[rname] = Room(
                room_name=rname,
                room_type=r_type,
                capacity=cap,
                building="",
            )

        # ── LECTURERS (deduplicate by name) ──
        lec_dept = {}
        lec_avail = {}
        for row in rows:
            name = row["lecturer"].strip()
            if not name:
                continue
            dept = _extract_dept(row["course"].strip())
            if name not in lec_dept:
                lec_dept[name] = dept
                lec_avail[name] = {}
            day = row.get("day", "").strip()
            hour = row.get("hour", "").strip()
            if day and hour:
                lec_avail[name].setdefault(day, set()).add(hour)

        used_emails = set()
        seen_lecturers = {}
        for name, dept in lec_dept.items():
            email = _name_to_email(name)
            base, suffix = email.split("@")
            n = 1
            while email in used_emails:
                email = f"{base}{n}@{suffix}"
                n += 1
            used_emails.add(email)
            lec = Lecturer(name=name, email=email, department=dept, specialisation="")
            lec.availability = {day: list(slots) for day, slots in lec_avail[name].items()}
            seen_lecturers[name] = lec

        # ── STUDENT GROUPS (one per unique level integer) ──
        level_counts = {}
        for row in rows:
            lvl = _parse_first_level(row["level"])
            try:
                count = int(float(row["students"]))
            except (ValueError, TypeError):
                count = 0
            if lvl not in level_counts or count > level_counts[lvl]:
                level_counts[lvl] = count

        seen_groups = {}
        for lvl, count in sorted(level_counts.items()):
            gname = f"{lvl}L"
            seen_groups[gname] = StudentGroup(
                group_name=gname,
                programme="General Studies",
                level=lvl,
                student_count=count,
            )

        # ── Clear old data and persist ──
        # TimetableEntry must go first — PostgreSQL FK constraints require it
        TimetableEntry.query.delete()
        Course.query.delete()
        Room.query.delete()
        Lecturer.query.delete()
        StudentGroup.query.delete()

        for obj in seen_courses.values():
            db.session.add(obj)
        for obj in seen_rooms.values():
            db.session.add(obj)
        for obj in seen_lecturers.values():
            db.session.add(obj)
        for obj in seen_groups.values():
            db.session.add(obj)

        db.session.commit()
        return jsonify({
            "success": True,
            "courses": len(seen_courses),
            "rooms": len(seen_rooms),
            "lecturers": len(seen_lecturers),
            "groups": len(seen_groups),
        })

    except Exception as ex:
        db.session.rollback()
        return jsonify({"success": False, "error": str(ex)}), 500
