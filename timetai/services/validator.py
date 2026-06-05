import json


class ConstraintValidator:
    def validate(self, timetable_entries: list, constraints: list = None) -> dict:
        hard_violations = []
        soft_violations = []

        hard_violations += self.check_room_clash(timetable_entries)
        hard_violations += self.check_lecturer_double_booking(timetable_entries)
        hard_violations += self.check_student_group_clash(timetable_entries)
        hard_violations += self.check_lab_room_type(timetable_entries)

        soft_violations += self.check_time_boundaries(timetable_entries)
        soft_violations += self.check_consecutive_hours(timetable_entries)

        return {
            "hard_violations": hard_violations,
            "soft_violations": soft_violations,
            "hard_satisfied": max(0, 6 - len(hard_violations)),
            "soft_satisfied": max(0, 5 - len(soft_violations)),
            "is_valid": len(hard_violations) == 0,
        }

    def _time_overlap(self, s1, e1, s2, e2):
        def to_mins(t):
            h, m = map(int, t.split(":"))
            return h * 60 + m
        return to_mins(s1) < to_mins(e2) and to_mins(s2) < to_mins(e1)

    def check_room_clash(self, entries):
        violations = []
        seen = {}
        for e in entries:
            key = (e.get("room"), e.get("day"))
            for other_key, other in seen.get(key, []):
                if self._time_overlap(e["start_time"], e["end_time"],
                                      other["start_time"], other["end_time"]):
                    violations.append({
                        "type": "HARD",
                        "title": "Room Double-Booking",
                        "description": f"Room {e['room']} is booked for both {e['course_code']} and {other['course_code']} on {e['day']} at overlapping times.",
                        "fix": f"Move one course to a different room or time slot.",
                    })
            seen.setdefault(key, []).append((None, e))
        return violations

    def check_lecturer_double_booking(self, entries):
        violations = []
        seen = {}
        for e in entries:
            key = (e.get("lecturer"), e.get("day"))
            for _, other in seen.get(key, []):
                if self._time_overlap(e["start_time"], e["end_time"],
                                      other["start_time"], other["end_time"]):
                    violations.append({
                        "type": "HARD",
                        "title": "Lecturer Double-Booking",
                        "description": f"{e['lecturer']} is scheduled for both {e['course_code']} and {other['course_code']} on {e['day']} at overlapping times.",
                        "fix": "Assign a different lecturer or reschedule one of the courses.",
                    })
            seen.setdefault(key, []).append((None, e))
        return violations

    def check_student_group_clash(self, entries):
        violations = []
        seen = {}
        for e in entries:
            key = (e.get("student_group"), e.get("day"))
            for _, other in seen.get(key, []):
                if self._time_overlap(e["start_time"], e["end_time"],
                                      other["start_time"], other["end_time"]):
                    violations.append({
                        "type": "HARD",
                        "title": "Student Group Clash",
                        "description": f"{e['student_group']} has overlapping classes: {e['course_code']} and {other['course_code']} on {e['day']}.",
                        "fix": "Reschedule one of the courses to a non-overlapping time.",
                    })
            seen.setdefault(key, []).append((None, e))
        return violations

    def check_lab_room_type(self, entries):
        violations = []
        for e in entries:
            if e.get("course_type") == "LAB" and "LAB" not in e.get("room", ""):
                violations.append({
                    "type": "HARD",
                    "title": "Lab in Wrong Room",
                    "description": f"{e['course_code']} is a LAB course but assigned to {e['room']} which is not a lab.",
                    "fix": "Assign this course to LAB-1 or LAB-2.",
                })
        return violations

    def check_time_boundaries(self, entries):
        violations = []
        for e in entries:
            start_h = int(e.get("start_time", "08:00").split(":")[0])
            end_h = int(e.get("end_time", "09:00").split(":")[0])
            if start_h < 8 or end_h > 17:
                violations.append({
                    "type": "SOFT",
                    "title": "Outside Preferred Hours",
                    "description": f"{e['course_code']} scheduled outside 8AM-5PM window ({e['start_time']}-{e['end_time']}).",
                    "fix": "Reschedule to fall within 08:00-17:00.",
                })
        return violations

    def check_consecutive_hours(self, entries):
        violations = []
        from collections import defaultdict
        group_day = defaultdict(list)
        for e in entries:
            group_day[(e.get("student_group"), e.get("day"))].append(e)
        for (grp, day), slots in group_day.items():
            slots.sort(key=lambda x: x["start_time"])
            consecutive = 0
            for i, slot in enumerate(slots):
                if i == 0:
                    consecutive = 1
                else:
                    prev_end = slots[i - 1]["end_time"]
                    if slot["start_time"] == prev_end:
                        consecutive += 1
                    else:
                        consecutive = 1
                if consecutive > 3:
                    violations.append({
                        "type": "SOFT",
                        "title": "Excessive Consecutive Hours",
                        "description": f"{grp} has {consecutive} consecutive hours on {day} ending at {slot['end_time']}.",
                        "fix": "Insert a break between lectures.",
                    })
        return violations

    def parse_natural_language_constraint(self, nl_text: str) -> dict:
        """Keyword-based NL parser — no API required."""
        text_lower = nl_text.lower()

        # Determine type
        hard_keywords = ["must", "never", "not allowed", "prohibited", "required", "cannot", "no room", "no lecturer"]
        ctype = "HARD" if any(k in text_lower for k in hard_keywords) else "SOFT"

        # Determine category
        if any(k in text_lower for k in ["room", "hall", "lab", "venue"]):
            category = "room"
        elif any(k in text_lower for k in ["lecturer", "teacher", "professor", "staff"]):
            category = "lecturer"
        elif any(k in text_lower for k in ["time", "am", "pm", "hour", "morning", "afternoon", "evening", "before", "after"]):
            category = "time"
        elif any(k in text_lower for k in ["capacity", "student", "size", "seats"]):
            category = "capacity"
        elif any(k in text_lower for k in ["friday", "monday", "tuesday", "wednesday", "thursday", "day"]):
            category = "distribution"
        elif any(k in text_lower for k in ["consecutive", "break", "gap", "back-to-back"]):
            category = "balance"
        else:
            category = "preference"

        return {
            "type": ctype,
            "category": category,
            "rule": nl_text,
            "description": nl_text,
        }
