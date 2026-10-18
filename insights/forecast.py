"""End-of-semester attendance forecasts and early warnings.

For each student and course: the lectures still to come (counted from the class
timetable until the semester ends, or from the recent pace when a class has no
timetable), the student's recent attendance rate, and from those a projected
final percentage, the best case if they attend everything, and roughly when they
will cross below the threshold.

Statuses:
    lost      - can't reach the threshold even attending every remaining lecture
    slipping  - at or above the threshold now, projected to finish below it
    at_risk   - below the threshold now and projected to stay below
    recovering- below now, projected to finish at or above
    ok        - at or above now and projected to stay there
"""
import datetime
import math
from collections import defaultdict

from django.conf import settings
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from sas.semester import semester_end
from timetable.models import TimeTable
from .analytics import load

SEVERITY = {'lost': 0, 'slipping': 1, 'at_risk': 2, 'recovering': 3, 'ok': 4}
MIN_LECTURES = 4   # fewer recorded lectures than this is too little to forecast from


def _remaining_from_timetable(cls_ids, today, end):
    """{(cls_id, course_id, batch): lectures left this semester} from timetable slots."""
    weekdays = defaultdict(int)       # weekday name -> number of days left with that name
    day = today + datetime.timedelta(days=1)
    while day <= end:
        weekdays[day.strftime('%A')] += 1
        day += datetime.timedelta(days=1)
    left = defaultdict(int)
    for cls_id, course_id, batch, weekday in TimeTable.objects.filter(cls__in=cls_ids) \
            .values_list('cls_id', 'course_id', 'batch', 'day'):
        left[(cls_id, course_id, batch)] += weekdays.get(weekday, 0)
    return left


def _remaining_from_pace(cls_ids, today, end):
    """For classes without a timetable: lectures per week over the last four weeks."""
    since = today - datetime.timedelta(days=28)
    weeks = max(0.0, (end - today).days / 7.0)
    counts = defaultdict(int)
    for cls_id, course_id, batch in AttendanceClass.objects.filter(
            assign__cls__in=cls_ids, date__gt=since, date__lte=today) \
            .values_list('assign__cls_id', 'assign__course_id', 'batch'):
        counts[(cls_id, course_id, batch)] += 1
    return {k: round(v / 4.0 * weeks) for k, v in counts.items()}


def _lectures_left(stu_cls, stu_batch, course_id, remaining):
    n = remaining.get((stu_cls, course_id, 'All'), 0)
    if stu_batch:
        n += remaining.get((stu_cls, course_id, stu_batch), 0)
    return n


def _rate(rows, today):
    """Recent pace, leaning on the last four weeks but steadied by the whole history."""
    overall = sum(r.present for r in rows) / len(rows)
    recent = [r for r in rows if r.date > today - datetime.timedelta(days=28)]
    if len(recent) < 3:
        return overall
    return 0.7 * (sum(r.present for r in recent) / len(recent)) + 0.3 * overall


def _project(present, total, remaining, rate, threshold, per_week):
    current = round(100 * present / total) if total else None
    projected = round(100 * (present + rate * remaining) / (total + remaining)) if total + remaining else None
    best = round(100 * (present + remaining) / (total + remaining)) if total + remaining else None
    target = threshold / 100
    crosses = None
    if current is not None and current >= threshold and per_week > 0:
        for week in range(1, 27):
            n = per_week * week
            if n > remaining:
                break
            if (present + rate * n) / (total + n) < target:
                crosses = week
                break
    if total < MIN_LECTURES:
        status = 'ok' if current is None or current >= threshold else 'at_risk'
        crosses = None
    elif best is not None and best < threshold:
        status = 'lost'
    elif current is not None and current >= threshold:
        status = 'slipping' if projected is not None and projected < threshold else 'ok'
    else:
        status = 'recovering' if projected is not None and projected >= threshold else 'at_risk'
    can_miss = None
    if remaining:
        can_miss = math.floor(present + remaining - target * (total + remaining) + 1e-9)
        can_miss = can_miss if can_miss >= 0 else None
    return {'current': current, 'projected': projected, 'best': best, 'remaining': remaining,
            'crosses_in_weeks': crosses, 'status': status, 'can_miss': can_miss}


def forecasts(students, today=None):
    """Forecast for each student in `students` (a queryset). Returns {student_id: forecast}."""
    today = today or timezone.localdate()
    end = semester_end(today)
    threshold = settings.ATTENDANCE_THRESHOLD
    students = list(students.select_related('user', 'cls'))
    cls_ids = {s.cls_id for s in students if s.cls_id}
    timetabled = set(TimeTable.objects.filter(cls__in=cls_ids).values_list('cls_id', flat=True))
    remaining = _remaining_from_timetable(timetabled, today, end)
    remaining.update(_remaining_from_pace(cls_ids - timetabled, today, end))
    weeks = max((end - today).days / 7.0, 1 / 7.0)

    rows = load(Attendance.objects.filter(student__in=students))
    by_student = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_student[r.student][r.course].append(r)
    names = dict(Assign_cls.objects.filter(cls__in=cls_ids)
                 .values_list('course_id', 'course__name'))
    codes = dict(Assign_cls.objects.filter(cls__in=cls_ids).values_list('course_id', 'course__code'))

    out = {}
    for stu in students:
        courses, totals = [], defaultdict(float)
        for course_id, crows in by_student[stu.id].items():
            present = sum(r.present for r in crows)
            left = _lectures_left(stu.cls_id, stu.batch, course_id, remaining) if stu.cls_id else 0
            rate = _rate(crows, today)
            f = _project(present, len(crows), left, rate, threshold, left / weeks)
            f.update(course_id=course_id, name=names.get(course_id) or str(course_id),
                     code=codes.get(course_id, ''), present=present, total=len(crows),
                     rate=round(rate * 100))
            courses.append(f)
            totals['present'] += present
            totals['total'] += len(crows)
            totals['remaining'] += left
            totals['expected'] += rate * left
        courses.sort(key=lambda c: (SEVERITY[c['status']], c['projected'] if c['projected'] is not None else 101))
        overall = None
        if totals['total']:
            overall = _project(int(totals['present']), int(totals['total']), int(totals['remaining']),
                               totals['expected'] / totals['remaining'] if totals['remaining'] else 0,
                               threshold, totals['remaining'] / weeks)
        status = min((c['status'] for c in courses), key=lambda s: SEVERITY[s], default='ok')
        out[stu.id] = {'student': stu, 'courses': courses, 'overall': overall, 'status': status,
                       'semester_end': end, 'weeks_left': round((end - today).days / 7.0, 1)}
    return out


def warnings(students, today=None, limit=None, courses=None):
    """Students who need attention soon, most urgent first.

    Each item is a forecast plus `reason`: the course that drives the warning
    (only courses in `courses`, a set of course ids, when given). Students whose
    only problem is being below now and staying there are left to the existing
    below-threshold lists; this is about what's coming.
    """
    items = []
    for f in forecasts(students, today).values():
        driver = next((c for c in f['courses'] if c['status'] in ('lost', 'slipping')
                       and (courses is None or c['course_id'] in courses)), None)
        if driver:
            items.append(dict(f, reason=driver))
    items.sort(key=lambda i: (SEVERITY[i['reason']['status']],
                              i['reason']['crosses_in_weeks'] or 99,
                              i['reason']['projected'] if i['reason']['projected'] is not None else 101))
    return items[:limit] if limit else items


def summary(forecast_list):
    """Compact, JSON-friendly digest for the AI analyst."""
    def ref(i):
        c = i['reason']
        return {'id': i['student'].id, 'name': i['student'].user.full_name, 'class': i['student'].cls.class_name if i['student'].cls else None,
                'course': c['name'], 'current': c['current'], 'projected': c['projected'], 'best': c['best'],
                'crosses_in_weeks': c['crosses_in_weeks'], 'status': c['status']}
    lost = [i for i in forecast_list if i['reason']['status'] == 'lost']
    slipping = [i for i in forecast_list if i['reason']['status'] == 'slipping']
    return {'cannot_recover': len(lost), 'will_slip': len(slipping),
            'cannot_recover_students': [ref(i) for i in lost[:6]],
            'will_slip_students': [ref(i) for i in slipping[:6]]}


def student_summary(f):
    """JSON-friendly digest of one student's forecast."""
    if not f or not f['overall']:
        return None
    return {
        'semester_end': f['semester_end'].isoformat(), 'weeks_left': f['weeks_left'],
        'projected_overall': f['overall']['projected'], 'best_overall': f['overall']['best'],
        'courses': [{k: c[k] for k in ('name', 'code', 'current', 'projected', 'best', 'remaining',
                                        'crosses_in_weeks', 'status', 'can_miss')} for c in f['courses']],
    }


def needed_rate(present, total, remaining, threshold=None):
    """Share of the remaining lectures needed to finish at the threshold (None if impossible)."""
    threshold = (threshold or settings.ATTENDANCE_THRESHOLD) / 100
    if not remaining:
        return None
    need = math.ceil(threshold * (total + remaining) - present)
    if need > remaining:
        return None
    return max(0, need)
