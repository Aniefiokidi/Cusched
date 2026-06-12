"""
CovenantSched — Dynamic CSP Backtracking Timetable Solver
Works for any level (100–500), any department, any courses in the database.
No hardcoded course-to-lecturer mappings — all assignments are computed dynamically.
"""
import os
import time
import random
from collections import defaultdict

try:
    from google import genai as _genai_module
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

from models.models import (
    db, Course, Room, Lecturer, StudentGroup, Constraint,
    TimetableEntry, GenerationSession,
)
from services.validator import ConstraintValidator

DAYS = ["MON", "TUE", "WED", "THU", "FRI"]
TIMES = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]


def _end_time(start: str) -> str:
    h = int(start.split(":")[0])
    return f"{(h+1):02d}:00"


def _time_to_min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _overlaps(s1, e1, s2, e2) -> bool:
    return _time_to_min(s1) < _time_to_min(e2) and _time_to_min(s2) < _time_to_min(e1)


class CSPTimetableSolver:
    def __init__(self):
        self.validator = ConstraintValidator()

    # ── Dynamic assignment builder ──────────────────────────────────────────────
    def build_variables(self, courses, lecturers, groups, level_filter="ALL", dept_filter="ALL"):
        """
        Dynamically assign each course to the best-fit lecturer and student group.
        No hardcoded mappings — works for any data in the database.
        """
        # Filter courses
        filtered = courses
        if level_filter and level_filter != "ALL":
            try:
                lvl = int(level_filter)
                filtered = [c for c in filtered if c["level"] == lvl]
            except ValueError:
                pass
        if dept_filter and dept_filter != "ALL":
            filtered = [c for c in filtered if c["department"].upper() == dept_filter.upper()]

        if not filtered:
            return []

        # Lecturer lookup: department → [lecturer, ...]
        lec_by_dept = defaultdict(list)
        for lec in lecturers:
            lec_by_dept[lec["department"].upper()].append(lec)
        all_lecs = list(lecturers)

        # Student group lookup: level → [group, ...]
        grp_by_level = defaultdict(list)
        for grp in groups:
            grp_by_level[grp["level"]].append(grp)
        all_levels = sorted(grp_by_level.keys())

        # Lecturer load tracking (courses assigned per lecturer)
        lec_load = defaultdict(int)

        variables = []
        for course in filtered:
            dept = course["department"].upper()
            level = course["level"]

            # ── Pick lecturer ──
            # Priority: same dept > any dept with lowest load
            candidates = lec_by_dept.get(dept, [])
            if not candidates:
                candidates = all_lecs
            lec = min(candidates, key=lambda l: lec_load[l["name"]])
            lec_load[lec["name"]] += 1

            # ── Pick student group ──
            level_groups = grp_by_level.get(level, [])
            if not level_groups:
                # Find nearest level
                nearest = min(all_levels, key=lambda lvl: abs(lvl - level), default=None)
                level_groups = grp_by_level.get(nearest, [])
            if not level_groups:
                level_groups = list(groups)

            # Match programme to department
            dept_grp = _match_group(level_groups, dept)

            variables.append({
                "course_code": course["course_code"],
                "course_title": course["course_title"],
                "course_type": course["course_type"],
                "level": level,
                "department": dept,
                "lecturer": lec["name"],
                "student_group": dept_grp["group_name"],
                "student_count": dept_grp["student_count"],
            })

        return variables


def _match_group(groups, dept):
    """Pick the student group whose programme best matches the department."""
    dept_lower = dept.lower()
    keywords = {
        "cis": ["computer science", "cs"],
        "mis": ["management information", "mis"],
        "mat": ["mathematics", "math"],
        "phy": ["physics"],
        "chm": ["chemistry"],
        "bch": ["biochemistry"],
        "bio": ["biology"],
        "arc": ["architecture"],
        "esm": ["environmental"],
    }
    kws = keywords.get(dept_lower, [dept_lower])
    for grp in groups:
        prog = grp["programme"].lower()
        if any(k in prog for k in kws):
            return grp
    return groups[0]


class CSPTimetableSolver(CSPTimetableSolver):
    # ── Domain builder ──────────────────────────────────────────────────────────
    def build_domain(self, var, rooms):
        domain = []
        room_cap = {r["room_name"]: r["capacity"] for r in rooms}
        for day in DAYS:
            for time in TIMES:
                end = _end_time(time)
                for room in rooms:
                    # LAB courses → LAB rooms only; LECTURE courses → non-LAB only
                    if var["course_type"] == "LAB" and room["room_type"] != "LAB":
                        continue
                    if var["course_type"] != "LAB" and room["room_type"] == "LAB":
                        continue
                    domain.append((day, time, end, room["room_name"]))
        # Prefer larger rooms, then shuffle
        domain.sort(key=lambda x: -room_cap.get(x[3], 0))
        random.shuffle(domain)
        return domain

    # ── Constraint check ────────────────────────────────────────────────────────
    def is_consistent(self, var, day, start, end, room_name, assigned):
        for a in assigned:
            if a["day"] != day:
                continue
            if not _overlaps(start, end, a["start_time"], a["end_time"]):
                continue
            if a["room"] == room_name:
                return False, "room clash"
            if a["lecturer"] == var["lecturer"]:
                return False, "lecturer double-booking"
            if a["student_group"] == var["student_group"]:
                return False, "student group clash"
        return True, ""

    # ── MRV ordering ────────────────────────────────────────────────────────────
    def order_variables(self, unassigned, assigned, rooms):
        def remaining(var):
            count = 0
            for (day, time, end, room) in self.build_domain(var, rooms):
                ok, _ = self.is_consistent(var, day, time, end, room, assigned)
                if ok:
                    count += 1
            return count
        return sorted(unassigned, key=remaining)

    # ── Backtracking search ─────────────────────────────────────────────────────
    def backtrack(self, unassigned, assigned, rooms, depth=0):
        if not unassigned:
            return assigned

        if depth % 3 == 0:
            unassigned = self.order_variables(unassigned, assigned, rooms)

        var = unassigned[0]
        rest = unassigned[1:]

        for (day, time, end, room_name) in self.build_domain(var, rooms):
            ok, _ = self.is_consistent(var, day, time, end, room_name, assigned)
            if ok:
                entry = {**var, "room": room_name, "day": day,
                         "start_time": time, "end_time": end}
                result = self.backtrack(rest, assigned + [entry], rooms, depth + 1)
                if result is not None:
                    return result

        return None

    # ── Main entry point ────────────────────────────────────────────────────────
    def solve(self, session_id: int) -> dict:
        session = db.session.get(GenerationSession, session_id)
        if not session:
            return {"error": "Session not found"}

        start_ts = time.time()
        session.status = "GENERATING"
        session.log_output = "[INFO] Loading data from database...\n"
        db.session.commit()

        courses = [c.to_dict() for c in Course.query.all()]
        rooms = [r.to_dict() for r in Room.query.all()]
        lecturers = [l.to_dict() for l in Lecturer.query.all()]
        groups = [g.to_dict() for g in StudentGroup.query.all()]
        constraints = [c.to_dict() for c in Constraint.query.filter_by(is_active=True).all()]

        level_filter = session.level_filter or "ALL"
        dept_filter = session.department or "ALL"

        # Count what we'll actually schedule
        filtered = courses
        if level_filter != "ALL":
            try:
                filtered = [c for c in filtered if c["level"] == int(level_filter)]
            except ValueError:
                pass

        session.log_output += (
            f"[INFO] Loaded: {len(courses)} total courses, {len(rooms)} rooms, "
            f"{len(lecturers)} lecturers, {len(groups)} groups\n"
            f"[INFO] Filter: Level={level_filter} | Dept={dept_filter}\n"
            f"[INFO] Courses to schedule: {len(filtered)}\n"
            f"[INFO] Constraints: "
            f"{len([c for c in constraints if c['constraint_type']=='HARD'])} hard, "
            f"{len([c for c in constraints if c['constraint_type']=='SOFT'])} soft\n"
        )
        db.session.commit()

        MAX_ATTEMPTS = 5
        final_entries = []
        result = {}

        for attempt in range(1, MAX_ATTEMPTS + 1):
            session.iteration_count = attempt
            random.seed(attempt * 31 + 7)

            variables = self.build_variables(courses, lecturers, groups, level_filter, dept_filter)
            if not variables:
                session.log_output += f"[ERROR] No courses match the selected filters (Level={level_filter}, Dept={dept_filter})\n"
                session.status = "FAILED"
                db.session.commit()
                return {"error": "No courses match filters", "session_id": session_id}

            session.log_output += f"\n[ITER {attempt}] Scheduling {len(variables)} courses with CSP backtracking...\n"
            db.session.commit()

            solution = self.backtrack(variables, [], rooms)

            if solution is not None:
                session.log_output += f"[ITER {attempt}] Solution found — {len(solution)} entries\n"
                session.status = "VALIDATING"
                db.session.commit()

                val = self.validator.validate(solution, constraints)
                session.hard_violations = len(val["hard_violations"])
                session.soft_violations = len(val["soft_violations"])
                session.log_output += (
                    f"[ITER {attempt}] Validation: {session.hard_violations} hard, "
                    f"{session.soft_violations} soft violations\n"
                )
                db.session.commit()

                final_entries = solution
                result = val

                if session.hard_violations == 0:
                    session.log_output += f"[ITER {attempt}] SUCCESS — All hard constraints satisfied!\n"
                    db.session.commit()
                    break
                else:
                    for v in val["hard_violations"][:3]:
                        session.log_output += f"  [VIOLATION] {v['title']}: {v['description']}\n"
                    session.log_output += f"[ITER {attempt}] Retrying with different seed...\n"
                    db.session.commit()
            else:
                session.log_output += f"[ITER {attempt}] No complete solution found — retrying...\n"
                db.session.commit()

        # Save timetable entries
        TimetableEntry.query.delete()
        db.session.commit()

        saved = 0
        for entry in final_entries:
            course = Course.query.filter_by(course_code=entry["course_code"]).first()
            lecturer = Lecturer.query.filter_by(name=entry["lecturer"]).first()
            room = Room.query.filter_by(room_name=entry["room"]).first()
            group = StudentGroup.query.filter_by(group_name=entry["student_group"]).first()
            if course and lecturer and room and group:
                db.session.add(TimetableEntry(
                    course_id=course.id, lecturer_id=lecturer.id,
                    room_id=room.id, student_group_id=group.id,
                    day_of_week=entry["day"], start_time=entry["start_time"],
                    end_time=entry["end_time"], semester=session.semester,
                    iteration_number=session.iteration_count,
                    is_validated=result.get("is_valid", False),
                ))
                saved += 1

        elapsed = time.time() - start_ts
        session.total_time_seconds = elapsed
        session.status = "COMPLETE"
        session.log_output += f"\n[DONE] Saved {saved} entries in {elapsed:.2f}s\n"
        db.session.commit()

        ai_note = GeminiTimetableExplainer().explain(
            final_entries, session.hard_violations, session.soft_violations,
            session.iteration_count, elapsed,
        )
        if ai_note:
            session.log_output += ai_note
            db.session.commit()

        return {
            "session_id": session_id,
            "iterations": session.iteration_count,
            "hard_violations": session.hard_violations,
            "soft_violations": session.soft_violations,
            "entries_saved": saved,
            "is_valid": result.get("is_valid", False),
            "elapsed": elapsed,
        }


class GeminiTimetableExplainer:
    """Calls Google Gemini (free tier) to produce a plain-English analysis after CSP scheduling."""

    MODEL = "gemini-flash-lite-latest"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.enabled = _GENAI_AVAILABLE and bool(api_key)
        if self.enabled:
            self._client = _genai_module.Client(api_key=api_key)

    def explain(self, entries: list, hard_violations: int, soft_violations: int,
                iteration_count: int, elapsed: float) -> str:
        if not self.enabled or not entries:
            return ""

        from collections import Counter
        days = Counter(e["day"] for e in entries)
        times = Counter(e["start_time"] for e in entries)
        unique_lecturers = len({e["lecturer"] for e in entries})
        unique_rooms = len({e["room"] for e in entries})

        day_line = ", ".join(f"{d}: {n}" for d, n in sorted(days.items()))
        peak_slots = ", ".join(f"{t} ({n})" for t, n in times.most_common(3))

        prompt = (
            "You are a concise academic timetable analyst.\n\n"
            f"Results: {len(entries)} courses scheduled across {iteration_count} "
            f"CSP iteration(s) in {elapsed:.1f}s.\n"
            f"Hard violations: {hard_violations} | Soft violations: {soft_violations}\n"
            f"Daily distribution: {day_line}\n"
            f"Peak time slots: {peak_slots}\n"
            f"Unique lecturers used: {unique_lecturers} | Unique rooms used: {unique_rooms}\n\n"
            "In exactly 3 sentences provide: (1) overall quality assessment, "
            "(2) any concern about violations or day distribution, "
            "(3) one specific actionable improvement. Be concise and practical."
        )

        try:
            response = self._client.models.generate_content(
                model=self.MODEL,
                contents=prompt,
            )
            return f"\n[AI Analysis - Gemini]\n{response.text.strip()}\n"
        except Exception as exc:
            return f"\n[AI Analysis unavailable: {exc}]\n"


# Public interface (keeps routes/generate.py unchanged)
class LLMTimetableService:
    def generate_timetable(self, session_id: int) -> dict:
        return CSPTimetableSolver().solve(session_id)
