"""Attendance facts for the insights pages and the AI analyst.

Everything here is deterministic and returns JSON-friendly dicts, so the same
facts drive the charts, the built-in analyst and the prompt sent to Claude.
"""
import datetime
from collections import defaultdict, namedtuple

from django.conf import settings
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from attendance.stats import is_short, lectures_needed, percent
from cls.models import Class
from course.models import Course
from sas.permissions import in_department
from student.models import student
from timetable.models import TimeTable
from users.models import TeacherProfile

WEEKS = 8
RECENT_DAYS = 14
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

Row = namedtuple('Row', 'present date start lecture student course assign')


def _start(period):
    """'09:00 - 10:00' -> '09:00'. Old 12-hour slots ('2:30 - 3:30') become 24-hour."""
    try:
        hour, minute = period.split('-')[0].strip().split(':')
        hour, minute = int(hour), int(minute)
    except (ValueError, AttributeError):
        return ''
    if hour < 8:
        hour += 12
    return '%02d:%02d' % (hour, minute)


def load(queryset):
    rows = queryset.filter(attendanceclass__status=1, excused=False).values_list(
        'status', 'attendanceclass__date', 'attendanceclass__period', 'attendanceclass_id',
        'student_id', 'course_id', 'attendanceclass__assign_id')
    return [Row(bool(p), d, _start(per), lec, s, c, a) for p, d, per, lec, s, c, a in rows]


def summarize(rows):
    present = sum(1 for r in rows if r.present)
    return {'present': present, 'total': len(rows), 'percent': percent(present, len(rows))}


def group(rows, key):
    out = defaultdict(list)
    for r in rows:
        out[key(r)].append(r)
    return out


def trend(rows, today):
    monday = today - datetime.timedelta(days=today.weekday())
    weeks = [monday - datetime.timedelta(weeks=i) for i in range(WEEKS - 1, -1, -1)]
    by_week = group(rows, lambda r: r.date - datetime.timedelta(days=r.date.weekday()))
    return [dict(week=w.isoformat(), label='%d %s' % (w.day, w.strftime('%b')),
                 **summarize(by_week.get(w, []))) for w in weeks]


def by_weekday(rows):
    by_day = group(rows, lambda r: r.date.weekday())
    return [dict(label=DAYS[d], short=DAYS[d][:3], **summarize(by_day[d])) for d in sorted(by_day)]


def by_time(rows):
    by_start = group(rows, lambda r: r.start)
    return [dict(label=s, **summarize(by_start[s])) for s in sorted(by_start) if s]


def recent_change(rows, today, minimum=5):
    """Last two weeks against the four weeks before them."""
    cutoff = today - datetime.timedelta(days=RECENT_DAYS)
    recent = [r for r in rows if r.date > cutoff]
    before = [r for r in rows if cutoff - datetime.timedelta(days=28) < r.date <= cutoff]
    if len(recent) < minimum or len(before) < minimum:
        return None
    a, b = summarize(recent)['percent'], summarize(before)['percent']
    return {'recent': a, 'before': b, 'delta': a - b}


def trailing_absences(rows):
    """Lectures missed in a row, counting back from the most recent one."""
    count = 0
    for r in sorted(rows, key=lambda r: (r.date, r.start, r.lecture), reverse=True):
        if r.present:
            break
        count += 1
    return count


def weak_spot(groups, overall, minimum=6, gap=8):
    """The weekday/time group furthest below the overall rate, if it stands out."""
    candidates = [g for g in groups if g['total'] >= minimum and g['percent'] is not None]
    if not candidates or overall is None:
        return None
    worst = min(candidates, key=lambda g: g['percent'])
    return worst if overall - worst['percent'] >= gap else None


def _per_student(rows):
    out = {}
    for sid, srows in group(rows, lambda r: r.student).items():
        s = summarize(srows)
        s['trailing'] = trailing_absences(srows)
        out[sid] = s
    return out


def _names(ids):
    return {s.id: s for s in student.objects.filter(id__in=ids).select_related('user', 'cls')}


def _student_ref(stu, stats):
    return {'id': stu.id, 'name': stu.user.full_name or stu.user.email,
            'class': stu.cls.class_name if stu.cls else None,
            'percent': stats['percent'], 'present': stats['present'], 'total': stats['total'],
            'trailing': stats.get('trailing', 0)}


def _missed_slots(assign, today, lecture_dates):
    """Timetabled lectures in the last two weeks with no attendance recorded."""
    slots = [s.day for s in TimeTable.objects.filter(cls=assign.cls, course=assign.course)]
    if not slots:
        return {'expected': 0, 'missed': 0}
    expected = missed = 0
    for offset in range(1, RECENT_DAYS + 1):
        day = today - datetime.timedelta(days=offset)
        wanted = slots.count(day.strftime('%A'))
        if wanted:
            expected += wanted
            missed += max(0, wanted - lecture_dates.get(day, 0))
    return {'expected': expected, 'missed': missed}


def _lecture_dates(assign_ids):
    counts = defaultdict(lambda: defaultdict(int))
    for a, d in AttendanceClass.objects.filter(assign__in=assign_ids).values_list('assign_id', 'date'):
        counts[a][d] += 1
    return counts


def _base(rows, today):
    overall = summarize(rows)
    return {
        'threshold': settings.ATTENDANCE_THRESHOLD,
        'as_of': today.isoformat(),
        'overall': overall,
        'trend': trend(rows, today),
        'by_weekday': by_weekday(rows),
        'by_time': by_time(rows),
        'recent_change': recent_change(rows, today),
    }


# ---------------------------------------------------------------- student

def student_facts(stu, today=None):
    today = today or timezone.localdate()
    rows = load(Attendance.objects.filter(student=stu))
    facts = _base(rows, today)
    facts.update(scope='student', name=stu.user.full_name or stu.user.email,
                 first_name=stu.user.first_name or stu.user.full_name,
                 class_name=stu.cls.class_name if stu.cls else None,
                 trailing_absences=trailing_absences(rows))
    o = facts['overall']
    o['needed'] = lectures_needed(o['present'], o['total'])

    courses = {c.id: c for c in Course.objects.filter(id__in={r.course for r in rows})}
    facts['courses'] = []
    for cid, crows in sorted(group(rows, lambda r: r.course).items(),
                             key=lambda kv: courses[kv[0]].name):
        s = summarize(crows)
        facts['courses'].append(dict(
            name=courses[cid].name, code=courses[cid].code, **s,
            needed=lectures_needed(s['present'], s['total']), short=is_short(s['percent']),
            change=recent_change(crows, today, minimum=3),
            trailing=trailing_absences(crows)))

    facts['class_average'] = None
    if stu.cls_id:
        class_rows = load(Attendance.objects.filter(student__cls=stu.cls_id))
        facts['class_average'] = summarize(class_rows)['percent']
    facts['weak_day'] = weak_spot(facts['by_weekday'], o['percent'], minimum=4)
    facts['weak_time'] = weak_spot(facts['by_time'], o['percent'], minimum=4)
    from . import forecast
    f = forecast.forecasts(student.objects.filter(pk=stu.pk), today).get(stu.pk)
    facts['forecast'] = forecast.student_summary(f)
    return facts


# ---------------------------------------------------------------- teacher

def teacher_facts(user, today=None):
    today = today or timezone.localdate()
    assigns = list(Assign_cls.objects.filter(teacher__user=user)
                   .select_related('cls', 'course').order_by('cls__class_name', 'course__name'))
    rows = load(Attendance.objects.filter(attendanceclass__assign__in=assigns))
    facts = _base(rows, today)
    facts.update(scope='teacher', name=user.full_name or user.email)

    by_assign = group(rows, lambda r: r.assign)
    dates = _lecture_dates([a.id for a in assigns])
    unmarked = defaultdict(int)
    for a_id in AttendanceClass.objects.filter(assign__in=assigns, status=0, date__lte=today) \
            .values_list('assign_id', flat=True):
        unmarked[a_id] += 1

    stats_by_assign = {a.id: _per_student(by_assign.get(a.id, [])) for a in assigns}
    names = _names({sid for stats in stats_by_assign.values() for sid in stats})
    threshold = settings.ATTENDANCE_THRESHOLD
    facts['courses'] = []
    below_ids = set()
    for a in assigns:
        arows = by_assign.get(a.id, [])
        stats = stats_by_assign[a.id]
        below = sorted((_student_ref(names[sid], s) for sid, s in stats.items()
                        if s['total'] >= 3 and s['percent'] < threshold),
                       key=lambda x: x['percent'])
        below_ids.update(x['id'] for x in below)
        streaks = sorted((_student_ref(names[sid], s) for sid, s in stats.items() if s['trailing'] >= 3),
                         key=lambda x: -x['trailing'])
        facts['courses'].append(dict(
            assign_id=a.id, course=a.course.name, code=a.course.code, class_name=a.cls.class_name,
            lectures=len({r.lecture for r in arows}), students=a.cls.student_set.count(),
            **summarize(arows), change=recent_change(arows, today),
            short=is_short(summarize(arows)['percent']),
            num_below=len(below), below=below[:6], streaks=streaks[:6],
            unmarked=unmarked[a.id], slots=_missed_slots(a, today, dates[a.id])))

    from . import forecast
    classes = {a.cls_id for a in assigns}
    facts['warnings'] = forecast.summary(forecast.warnings(
        student.objects.filter(cls__in=classes), today, courses={a.course_id for a in assigns}))
    facts['students_below'] = len(below_ids)
    facts['unmarked'] = sum(unmarked.values())
    facts['missed_slots'] = sum(c['slots']['missed'] for c in facts['courses'])
    facts['weak_day'] = weak_spot(facts['by_weekday'], facts['overall']['percent'])
    facts['weak_time'] = weak_spot(facts['by_time'], facts['overall']['percent'])
    return facts


def _department_warnings(user, today):
    from . import forecast
    students = in_department(student.objects.filter(user__is_staff=False, cls__isnull=False),
                             user, 'user__department')
    return forecast.summary(forecast.warnings(students, today))


# ---------------------------------------------------------------- department

def department_facts(user, today=None):
    today = today or timezone.localdate()
    threshold = settings.ATTENDANCE_THRESHOLD
    classes = list(in_department(Class.objects.all(), user)
                   .select_related('class_teacher__user').order_by('class_name'))
    assigns = list(Assign_cls.objects.filter(cls__in=classes)
                   .select_related('cls', 'course', 'teacher__user'))
    rows = load(Attendance.objects.filter(attendanceclass__assign__in=assigns))
    facts = _base(rows, today)
    facts.update(scope='department', name=user.department or 'All departments')

    assign_by_id = {a.id: a for a in assigns}
    per_student = _per_student(rows)
    names = _names(per_student)

    # Classes
    rows_by_class = group(rows, lambda r: assign_by_id[r.assign].cls_id)
    timetabled = set(TimeTable.objects.filter(cls__in=classes).values_list('cls_id', flat=True))
    facts['classes'] = []
    for c in classes:
        crows = rows_by_class.get(c.id, [])
        cstats = _per_student(crows)
        facts['classes'].append(dict(
            id=c.id, name=c.class_name, students=c.student_set.count(), **summarize(crows),
            change=recent_change(crows, today), short=is_short(summarize(crows)['percent']),
            num_below=sum(1 for s in cstats.values() if s['total'] >= 5 and s['percent'] < threshold),
            class_teacher=c.class_teacher.user.full_name if c.class_teacher else None,
            has_timetable=c.id in timetabled))

    # Courses, lowest first
    by_assign = group(rows, lambda r: r.assign)
    course_rows = []
    for a in assigns:
        arows = by_assign.get(a.id, [])
        if len({r.lecture for r in arows}) >= 3:
            course_rows.append(dict(course=a.course.name, code=a.course.code,
                                    class_name=a.cls.class_name,
                                    teacher=a.teacher.user.full_name, **summarize(arows),
                                    change=recent_change(arows, today),
                                    short=is_short(summarize(arows)['percent'])))
    course_rows.sort(key=lambda c: c['percent'])
    facts['lowest_courses'] = course_rows[:5]
    facts['highest_courses'] = course_rows[::-1][:3]

    # Teachers: marking discipline
    dates = _lecture_dates([a.id for a in assigns])
    unmarked = defaultdict(int)
    for a_id in AttendanceClass.objects.filter(assign__in=assigns, status=0, date__lte=today) \
            .values_list('assign_id', flat=True):
        unmarked[a_id] += 1
    teachers = defaultdict(lambda: {'unmarked': 0, 'missed_slots': 0, 'expected_slots': 0, 'courses': 0})
    for a in assigns:
        t = teachers[a.teacher.user.full_name]
        t['courses'] += 1
        t['unmarked'] += unmarked[a.id]
        slots = _missed_slots(a, today, dates[a.id])
        t['missed_slots'] += slots['missed']
        t['expected_slots'] += slots['expected']
    facts['teachers'] = sorted(
        (dict(name=n, **t) for n, t in teachers.items()),
        key=lambda t: -(t['unmarked'] + t['missed_slots']))

    # Students at risk
    at_risk = sorted((_student_ref(names[sid], s) for sid, s in per_student.items()
                      if s['total'] >= 5 and s['percent'] < threshold), key=lambda x: x['percent'])
    facts['at_risk'] = {
        'count': len(at_risk),
        'critical': sum(1 for s in at_risk if s['percent'] < 60),
        'students': at_risk[:8],
        'streaks': sorted((_student_ref(names[sid], s) for sid, s in per_student.items()
                           if s['trailing'] >= 4), key=lambda x: -x['trailing'])[:6],
    }

    # Setup gaps worth fixing
    dept_courses = in_department(Course.objects.all(), user, 'dept')
    staff = in_department(TeacherProfile.objects.filter(user__is_staff=True, user__is_superuser=False),
                          user, 'user__department')
    facts['gaps'] = {
        'classes_without_timetable': [c['name'] for c in facts['classes']
                                      if not c['has_timetable'] and c['students']],
        'classes_without_teacher': [c['name'] for c in facts['classes'] if not c['class_teacher']],
        'unassigned_courses': list(dept_courses.filter(assign_cls__isnull=True)
                                   .values_list('name', flat=True)[:6]),
        'idle_teachers': [t.user.full_name for t in staff.filter(assign_cls__isnull=True)
                          .select_related('user')][:6],
        'students_without_class': in_department(
            student.objects.filter(user__is_staff=False, cls__isnull=True),
            user, 'user__department').count(),
    }
    facts['weak_day'] = weak_spot(facts['by_weekday'], facts['overall']['percent'])
    facts['weak_time'] = weak_spot(facts['by_time'], facts['overall']['percent'])
    facts['warnings'] = _department_warnings(user, today)
    return facts
