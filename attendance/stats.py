"""Attendance percentages used by the dashboard and reports."""
import math

from django.conf import settings
from django.db.models import Count, Q

from student.models import ROLL_ORDER
from .models import Attendance


def percent(present, total):
    return round(present * 100 / total) if total else None


def is_short(pct):
    return pct is not None and pct < settings.ATTENDANCE_THRESHOLD


def lectures_needed(present, total):
    """Consecutive lectures to attend to get back up to the threshold."""
    target = settings.ATTENDANCE_THRESHOLD / 100
    if not total or present / total >= target:
        return 0
    return math.ceil((target * total - present) / (1 - target))


def assignment_report(assign):
    """Per-student attendance for one class + course, ordered by roll number."""
    lectures = assign.attendanceclass_set.filter(status=1)
    # Count each student's own records so someone who joined the class late
    # is not marked absent for lectures held before they arrived.
    counts = {
        row['student']: row
        for row in Attendance.objects.filter(attendanceclass__in=lectures)
        .values('student').annotate(
            total=Count('attendanceclass', distinct=True),
            present=Count('attendanceclass', distinct=True, filter=Q(status=True)))
    }
    rows = []
    for stu in assign.cls.student_set.select_related('user').order_by(*ROLL_ORDER):
        row = counts.get(stu.id, {'present': 0, 'total': 0})
        pct = percent(row['present'], row['total'])
        rows.append({'student': stu, 'present': row['present'], 'total': row['total'],
                     'percent': pct, 'short': is_short(pct)})
    return rows, lectures.count()


def student_summary(stu):
    """Attendance per course for one student, plus an overall figure."""
    per_course = (
        Attendance.objects.filter(student=stu)
        .values('course__id', 'course__code', 'course__name')
        .annotate(total=Count('attendanceclass', distinct=True),
                  present=Count('attendanceclass', distinct=True, filter=Q(status=True)))
        .order_by('course__name')
    )
    courses, present_sum, total_sum = [], 0, 0
    for row in per_course:
        pct = percent(row['present'], row['total'])
        courses.append({'code': row['course__code'], 'name': row['course__name'],
                        'present': row['present'], 'total': row['total'],
                        'percent': pct, 'short': is_short(pct),
                        'needed': lectures_needed(row['present'], row['total'])})
        present_sum += row['present']
        total_sum += row['total']
    overall = percent(present_sum, total_sum)
    return {'courses': courses, 'present': present_sum, 'total': total_sum,
            'percent': overall, 'short': is_short(overall),
            'needed': lectures_needed(present_sum, total_sum)}


def students_below_threshold(students, limit=None):
    """Students whose overall attendance is under the threshold, worst first."""
    annotated = students.select_related('user', 'cls').annotate(
        total=Count('attendance__attendanceclass', distinct=True),
        present=Count('attendance__attendanceclass', distinct=True,
                      filter=Q(attendance__status=True)),
    ).filter(total__gt=0)
    rows = []
    for stu in annotated:
        pct = percent(stu.present, stu.total)
        if is_short(pct):
            rows.append({'student': stu, 'present': stu.present, 'total': stu.total, 'percent': pct})
    rows.sort(key=lambda r: r['percent'])
    return rows[:limit] if limit else rows
