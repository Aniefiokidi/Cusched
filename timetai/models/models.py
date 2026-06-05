from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import json

db = SQLAlchemy()


class Admin(db.Model, UserMixin):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    credit_units = db.Column(db.Integer, nullable=False)
    course_type = db.Column(db.String(20), nullable=False, default="LECTURE")
    department = db.Column(db.String(50), nullable=False)
    level = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "course_code": self.course_code,
            "course_title": self.course_title,
            "credit_units": self.credit_units,
            "course_type": self.course_type,
            "department": self.department,
            "level": self.level,
        }


class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(50), unique=True, nullable=False)
    room_type = db.Column(db.String(30), nullable=False, default="LECTURE_HALL")
    capacity = db.Column(db.Integer, nullable=False)
    building = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "room_name": self.room_name,
            "room_type": self.room_type,
            "capacity": self.capacity,
            "building": self.building,
        }


class Lecturer(db.Model):
    __tablename__ = "lecturers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(50), nullable=False)
    specialisation = db.Column(db.String(100))
    availability_raw = db.Column(db.Text, default="{}")

    @property
    def availability(self):
        try:
            return json.loads(self.availability_raw or "{}")
        except Exception:
            return {}

    @availability.setter
    def availability(self, value):
        if isinstance(value, dict):
            self.availability_raw = json.dumps(value)
        else:
            self.availability_raw = value or "{}"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "specialisation": self.specialisation,
            "availability": self.availability,
        }


class StudentGroup(db.Model):
    __tablename__ = "student_groups"
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(50), unique=True, nullable=False)
    programme = db.Column(db.String(100), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    student_count = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "group_name": self.group_name,
            "programme": self.programme,
            "level": self.level,
            "student_count": self.student_count,
        }


class Constraint(db.Model):
    __tablename__ = "constraints"
    id = db.Column(db.Integer, primary_key=True)
    constraint_type = db.Column(db.String(10), nullable=False, default="HARD")
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    is_natural_language = db.Column(db.Boolean, default=False)
    parsed_rule_raw = db.Column(db.Text, default="{}")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def parsed_rule(self):
        try:
            return json.loads(self.parsed_rule_raw or "{}")
        except Exception:
            return {}

    @parsed_rule.setter
    def parsed_rule(self, value):
        if isinstance(value, dict):
            self.parsed_rule_raw = json.dumps(value)
        else:
            self.parsed_rule_raw = value or "{}"

    def to_dict(self):
        return {
            "id": self.id,
            "constraint_type": self.constraint_type,
            "category": self.category,
            "description": self.description,
            "is_natural_language": self.is_natural_language,
            "parsed_rule": self.parsed_rule,
            "is_active": self.is_active,
        }


class TimetableEntry(db.Model):
    __tablename__ = "timetable_entries"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"))
    lecturer_id = db.Column(db.Integer, db.ForeignKey("lecturers.id"))
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"))
    student_group_id = db.Column(db.Integer, db.ForeignKey("student_groups.id"))
    day_of_week = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    week_type = db.Column(db.String(10), default="ALL")
    semester = db.Column(db.String(20), default="FIRST")
    iteration_number = db.Column(db.Integer, default=1)
    is_validated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref="entries")
    lecturer = db.relationship("Lecturer", backref="entries")
    room = db.relationship("Room", backref="entries")
    student_group = db.relationship("StudentGroup", backref="entries")

    def to_dict(self):
        return {
            "id": self.id,
            "course_code": self.course.course_code if self.course else "",
            "course_title": self.course.course_title if self.course else "",
            "lecturer": self.lecturer.name if self.lecturer else "",
            "room": self.room.room_name if self.room else "",
            "student_group": self.student_group.group_name if self.student_group else "",
            "day": self.day_of_week,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "level": self.course.level if self.course else 0,
            "course_type": self.course.course_type if self.course else "",
        }


class GenerationSession(db.Model):
    __tablename__ = "generation_sessions"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), default="ALPHA")
    department = db.Column(db.String(50), default="CIS")
    level_filter = db.Column(db.String(10), default="ALL")
    status = db.Column(db.String(20), default="PENDING")
    iteration_count = db.Column(db.Integer, default=0)
    hard_violations = db.Column(db.Integer, default=0)
    soft_violations = db.Column(db.Integer, default=0)
    total_time_seconds = db.Column(db.Float, default=0)
    log_output = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
