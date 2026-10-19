"""Ask SAS: questions about attendance, answered from read-only data tools.

Every tool is scoped to what the asking user may see (a student: themself; a
teacher: the classes they teach; an HOD or class teacher: the department).
With AI_TOKEN set, Claude decides which tools to call and writes the answer;
otherwise a built-in parser maps common questions onto the same tools.

`answer(user, question, history)` returns
    {answer: str, tables: [{title, columns, rows, note}], source, notice?}
"""
import datetime
import json
import logging
import re
from collections import defaultdict

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from attendance.stats import percent
from cls.models import Class
from sas import ai
from sas.permissions import in_department
from student.models import student
from users.models import TeacherProfile

log = logging.getLogger(__name__)
MAX_ROWS = 40


# ------------------------------------------------------------------ scope

class Scope:
    def __init__(self, user):
        self.user = user
        self.me = None
        if user.is_student:
            self.me = student.objects.filter(user=user).select_related('cls', 'user').first()
            self.students = student.objects.filter(pk=self.me.pk if self.me else -1)
            self.assigns = Assign_cls.objects.filter(cls=self.me.cls_id if self.me else -1)
        elif user.can_manage_students:
            self.students = in_department(student.objects.filter(user__is_staff=False), user, 'user__department')
            self.assigns = in_department(Assign_cls.objects.all(), user, 'cls__department')
        else:
            self.assigns = Assign_cls.objects.filter(teacher__user=user)
            self.students = student.objects.filter(cls__in=self.assigns.values('cls'), user__is_staff=False)
        self.assigns = self.assigns.select_related('cls', 'course', 'teacher__user')

    def classes(self):
        return Class.objects.filter(pk__in=self.assigns.values('cls')).order_by('class_name')

    # Fuzzy lookups -----------------------------------------------------
    def find_class(self, text):
        if not text:
            return None
        key = re.sub(r'[^a-z0-9]', '', text.lower())
        return next((c for c in self.classes() if key and key in re.sub(r'[^a-z0-9]', '', c.class_name.lower())), None)

    def find_assigns(self, course=None, class_name=None):
        qs = self.assigns
        if class_name:
            cls = self.find_class(class_name)
            qs = qs.filter(cls=cls) if cls else qs.none()
        if course:
            ids = [a.id for a in qs if _course_matches(a.course, course)]
            qs = qs.filter(id__in=ids)
        return qs

    def find_student(self, name):
        words = [w for w in re.findall(r'[a-z]+', (name or '').lower()) if len(w) > 1]
        if not words:
            return None
        best = None
        for s in self.students.select_related('user', 'cls'):
            full = s.user.full_name.lower()
            hits = sum(1 for w in words if w in full.split())
            if hits and (best is None or hits > best[0]):
                best = (hits, s)
        return best[1] if best else None


def _initials(name):
    words = [w for w in re.findall(r'[A-Za-z]+', name) if w.lower() not in ('and', 'of', 'the', 'lab')]
    return ''.join(w[0] for w in words).lower()


def _course_matches(course, text):
    t = text.strip().lower()
    return t == course.code.lower() or t in course.name.lower() or (len(t) >= 2 and t == _initials(course.name))


def _since(days):
    return timezone.localdate() - datetime.timedelta(days=int(days))


def _records(scope, assigns=None, since_days=None):
    qs = Attendance.objects.filter(student__in=scope.students, attendanceclass__status=1, excused=False)
    if assigns is not None:
        qs = qs.filter(attendanceclass__assign__in=assigns)
    else:
        qs = qs.filter(attendanceclass__assign__in=scope.assigns)
    if since_days:
        qs = qs.filter(attendanceclass__date__gt=_since(since_days))
    return qs


def _table(title, columns, rows, note=''):
    truncated = len(rows) > MAX_ROWS
    return {'title': title, 'columns': columns, 'rows': rows[:MAX_ROWS],
            'note': (note + (' ' if note else '') + 'Showing the first %d of %d.' % (MAX_ROWS, len(rows)))
            if truncated else note, 'count': len(rows)}


# ------------------------------------------------------------------ tools

def find_students(scope, below_percent=None, above_percent=None, class_name=None, course=None):
    assigns = scope.find_assigns(course, class_name)
    agg = (_records(scope, assigns).values('student_id')
           .annotate(total=Count('id'), present=Count('id', filter=Q(status=True))))
    names = {s.id: s for s in scope.students.select_related('user', 'cls')}
    rows = []
    for r in agg:
        pct = percent(r['present'], r['total'])
        if below_percent is not None and not pct < below_percent:
            continue
        if above_percent is not None and not pct >= above_percent:
            continue
        s = names.get(r['student_id'])
        if s:
            rows.append([s.user.full_name, s.cls.class_name if s.cls else '-', s.roll_no or '',
                         '%d/%d' % (r['present'], r['total']), pct])
    rows.sort(key=lambda r: r[4])
    what = 'Students'
    if below_percent is not None:
        what += ' below %d%%' % below_percent
    if above_percent is not None:
        what += ' at or above %d%%' % above_percent
    if course:
        what += ' in %s' % course
    if class_name:
        what += ' (%s)' % class_name
    return _table(what, ['Student', 'Class', 'Roll', 'Attended', '%'], rows)


def absences(scope, course=None, class_name=None, since_days=30, min_absences=1):
    assigns = scope.find_assigns(course, class_name)
    agg = (_records(scope, assigns, since_days).values('student_id', 'attendanceclass__assign_id')
           .annotate(total=Count('id'), absent=Count('id', filter=Q(status=False))))
    names = {s.id: s for s in scope.students.select_related('user', 'cls')}
    by_assign = {a.id: a for a in scope.assigns}
    rows = []
    for r in agg:
        if r['absent'] >= (min_absences or 1):
            s, a = names.get(r['student_id']), by_assign.get(r['attendanceclass__assign_id'])
            if s and a:
                rows.append([s.user.full_name, a.cls.class_name, a.course.name, r['absent'], r['total']])
    rows.sort(key=lambda r: (-r[3], r[0]))
    title = 'Missed %s+ lectures in the last %d days' % (min_absences or 1, since_days)
    if course:
        title += ' · %s' % course
    return _table(title, ['Student', 'Class', 'Course', 'Missed', 'Lectures'], rows)


def student_attendance(scope, name=None):
    stu = scope.me if scope.me and not name else scope.find_student(name)
    if stu is None:
        return {'error': "I couldn't find a student called '%s' among the students you can see." % (name or '')}
    from .forecast import forecasts
    f = forecasts(student.objects.filter(pk=stu.pk)).get(stu.pk)
    rows = []
    for c in (f['courses'] if f else []):
        rows.append([c['name'], '%d/%d' % (c['present'], c['total']), c['current'],
                     c['projected'] if c['total'] >= 4 else '-',
                     {'lost': "Can't reach %d%%" % settings.ATTENDANCE_THRESHOLD,
                      'slipping': 'Slipping', 'at_risk': 'Below', 'recovering': 'Recovering',
                      'ok': 'On track'}[c['status']],
                     c['can_miss'] if c['can_miss'] is not None else '-'])
    overall = f['overall'] if f else None
    t = _table('%s · %s' % (stu.user.full_name, stu.cls.class_name if stu.cls else 'no class'),
               ['Course', 'Attended', '% now', '% by end', 'Status', 'Can still miss'], rows)
    t['student'] = stu.user.full_name
    t['overall_now'] = overall['current'] if overall else None
    t['overall_projected'] = overall['projected'] if overall else None
    return t


def class_summary(scope):
    agg = (_records(scope).values('attendanceclass__assign__cls_id', 'student_id')
           .annotate(total=Count('id'), present=Count('id', filter=Q(status=True))))
    per = defaultdict(lambda: {'present': 0, 'total': 0, 'students': set(), 'below': 0})
    for r in agg:
        c = per[r['attendanceclass__assign__cls_id']]
        c['present'] += r['present']
        c['total'] += r['total']
        c['students'].add(r['student_id'])
    # Students below the threshold, per class, across all their courses.
    student_tot = defaultdict(lambda: [0, 0, None])
    for r in agg:
        st = student_tot[r['student_id']]
        st[0] += r['present']
        st[1] += r['total']
        st[2] = r['attendanceclass__assign__cls_id']
    for present, total, cls_id in student_tot.values():
        if total and percent(present, total) < settings.ATTENDANCE_THRESHOLD:
            per[cls_id]['below'] += 1
    rows = []
    for cls in scope.classes():
        c = per.get(cls.id)
        if c:
            rows.append([cls.class_name, len(c['students']), percent(c['present'], c['total']), c['below']])
    rows.sort(key=lambda r: r[2])
    return _table('Classes by attendance', ['Class', 'Students', '%', 'Below %d%%' % settings.ATTENDANCE_THRESHOLD], rows)


def lecture_log(scope, course=None, class_name=None, since_days=14):
    assigns = scope.find_assigns(course, class_name)
    lectures = (AttendanceClass.objects.filter(assign__in=assigns, date__gt=_since(since_days))
                .select_related('assign__course', 'assign__cls', 'assign__teacher__user')
                .annotate(present=Count('attendance', filter=Q(attendance__status=True)),
                          marked=Count('attendance'))
                .order_by('-date', '-period'))
    rows = [[l.date.strftime('%a %d %b'), l.period, l.assign.course.name, l.assign.cls.class_name,
             '%d/%d' % (l.present, l.marked) if l.status else 'Not marked'] for l in lectures]
    return _table('Lectures in the last %d days' % since_days, ['Date', 'Time', 'Course', 'Class', 'Present'], rows)


def teacher_marking(scope, since_days=14):
    from .analytics import _lecture_dates, _missed_slots
    today = timezone.localdate()
    assigns = list(scope.assigns)
    dates = _lecture_dates([a.id for a in assigns])
    unmarked = defaultdict(int)
    for a_id in AttendanceClass.objects.filter(assign__in=assigns, status=0, date__lte=today) \
            .values_list('assign_id', flat=True):
        unmarked[a_id] += 1
    per = defaultdict(lambda: [0, 0])
    for a in assigns:
        per[a.teacher.user.full_name][0] += unmarked[a.id]
        per[a.teacher.user.full_name][1] += _missed_slots(a, today, dates[a.id])['missed']
    rows = sorted(([n, u, m] for n, (u, m) in per.items()), key=lambda r: -(r[1] + r[2]))
    return _table('Record keeping (last 14 days)', ['Teacher', 'Unmarked lectures', 'Timetabled, not recorded'], rows)


def early_warnings(scope):
    from .forecast import warnings
    rows = []
    for w in warnings(scope.students.filter(cls__isnull=False)):
        c = w['reason']
        rows.append([w['student'].user.full_name, w['student'].cls.class_name, c['name'], c['current'],
                     c['projected'], "Can't reach %d%%" % settings.ATTENDANCE_THRESHOLD if c['status'] == 'lost'
                     else 'Below in ~%s wk' % c['crosses_in_weeks'] if c['crosses_in_weeks'] else 'Will slip'])
    return _table('Early warnings to the end of the semester',
                  ['Student', 'Class', 'Course', '% now', '% by end', 'Warning'], rows)


TOOLS = {
    'find_students': find_students,
    'absences': absences,
    'student_attendance': student_attendance,
    'class_summary': class_summary,
    'lecture_log': lecture_log,
    'teacher_marking': teacher_marking,
    'early_warnings': early_warnings,
}


def _obj(props, required=()):
    return {'type': 'object', 'properties': props, 'required': list(required), 'additionalProperties': False}


TOOL_DEFS = [
    {'name': 'find_students', 'description': 'List students with their overall attendance percentage (or in one course), optionally filtered to those below or at/above a percentage, a class, or a course.',
     'input_schema': _obj({'below_percent': {'type': 'integer'}, 'above_percent': {'type': 'integer'},
                           'class_name': {'type': 'string'}, 'course': {'type': 'string', 'description': 'Course name, code or initials, e.g. "CN".'}})},
    {'name': 'absences', 'description': 'Count each student\'s missed lectures per course over the last N days, keeping those with at least min_absences.',
     'input_schema': _obj({'course': {'type': 'string'}, 'class_name': {'type': 'string'},
                           'since_days': {'type': 'integer', 'description': 'Look back this many days (default 30).'},
                           'min_absences': {'type': 'integer'}})},
    {'name': 'student_attendance', 'description': "One student's attendance per course now, forecast to the end of the semester, and how many more lectures they can miss. Students may only ask about themselves (omit name).",
     'input_schema': _obj({'name': {'type': 'string'}})},
    {'name': 'class_summary', 'description': 'Attendance per class, with how many students are below the threshold.',
     'input_schema': _obj({})},
    {'name': 'lecture_log', 'description': 'Lectures held recently, with how many were present and which are not marked yet.',
     'input_schema': _obj({'course': {'type': 'string'}, 'class_name': {'type': 'string'}, 'since_days': {'type': 'integer'}})},
    {'name': 'teacher_marking', 'description': 'Per teacher: lectures started but not marked, and timetabled lectures with no attendance recorded in the last two weeks.',
     'input_schema': _obj({})},
    {'name': 'early_warnings', 'description': 'Students forecast to drop below the threshold by the end of the semester, or who can no longer reach it.',
     'input_schema': _obj({})},
    {'name': 'show_table', 'description': 'Show a table to the user under your answer. Use it for any list of more than three items, copying rows from tool results.',
     'input_schema': _obj({'title': {'type': 'string'}, 'columns': {'type': 'array', 'items': {'type': 'string'}},
                           'rows': {'type': 'array', 'items': {'type': 'array', 'items': {'type': ['string', 'number']}}}},
                          ['title', 'columns', 'rows'])},
]

SYSTEM = """You answer questions about student attendance inside SAS, a college attendance system. \
Today is {today}. The attendance requirement is {threshold}%. The person asking is {who}.

Use the tools to look things up; never guess numbers or names. Tools only return data this person \
is allowed to see; if something isn't there, say so. When the answer is a list, call show_table \
with the rows and keep your written answer to a short summary (two or three sentences, plain text, \
no markdown tables). If the question isn't about attendance, timetables or students here, say \
briefly what you can help with."""


def _who(user):
    if user.is_student:
        return 'a student asking about their own attendance'
    if user.can_manage_department:
        return 'the head of department (%s)' % (user.department or 'all departments')
    if user.can_manage_students:
        return 'a class teacher in %s' % user.department
    return 'a teacher asking about the classes they teach'


def run_tool(scope, name, args):
    if name not in TOOLS:
        return {'error': 'Unknown tool %s' % name}
    args = {k: v for k, v in (args or {}).items() if v not in (None, '')}
    try:
        return TOOLS[name](scope, **args)
    except TypeError as e:
        return {'error': 'Bad arguments: %s' % e}


# ------------------------------------------------------------------ Claude

def _claude(user, scope, question, history):
    import anthropic
    client = anthropic.Anthropic(api_key=settings.AI_TOKEN, timeout=60.0, max_retries=2)
    tools = [dict(t, strict=True) for t in TOOL_DEFS]
    messages = []
    for turn in history[-3:]:
        messages += [{'role': 'user', 'content': turn['q'][:500]}, {'role': 'assistant', 'content': turn['a'][:1500]}]
    messages.append({'role': 'user', 'content': question})
    system = SYSTEM.format(today=timezone.localdate().strftime('%A %d %B %Y'),
                           threshold=settings.ATTENDANCE_THRESHOLD, who=_who(user))
    tables = []
    for _ in range(6):
        response = client.beta.messages.create(
            model=settings.AI_MODEL, max_tokens=8000, system=system, tools=tools, messages=messages,
            output_config={'effort': 'low'},
            betas=['server-side-fallback-2026-07-01'], fallbacks='default')
        if response.stop_reason == 'refusal':
            raise ai.AIError('The AI declined to answer that.')
        uses = [b for b in response.content if b.type == 'tool_use']
        if response.stop_reason != 'tool_use' or not uses:
            text = '\n'.join(b.text for b in response.content if b.type == 'text').strip()
            return {'answer': text or 'Done.', 'tables': tables}
        messages.append({'role': 'assistant', 'content': response.content})
        results = []
        for block in uses:
            if block.name == 'show_table':
                inp = block.input
                tables.append(_table(str(inp.get('title', ''))[:120], [str(c) for c in inp.get('columns', [])][:8],
                                     [[str(v) for v in row][:8] for row in inp.get('rows', [])]))
                out = {'shown': True}
            else:
                out = run_tool(scope, block.name, block.input)
            results.append({'type': 'tool_result', 'tool_use_id': block.id,
                            'content': json.dumps(out, default=str)[:20000],
                            **({'is_error': True} if isinstance(out, dict) and 'error' in out else {})})
        messages.append({'role': 'user', 'content': results})
    return {'answer': 'That took too many steps. Try a more specific question.', 'tables': tables}


# ------------------------------------------------------------------ built-in

_NUM = r'(\d+)'


def _days_in(q):
    if re.search(r'\btoday\b', q):
        return 1
    if re.search(r'\bthis week|past week|last week|7 days\b', q):
        return 7
    if re.search(r'fortnight|two weeks|2 weeks|14 days', q):
        return 14
    m = re.search(r'(?:last|past)\s+(\d+)\s+days?', q)
    if m:
        return int(m.group(1))
    if re.search(r'this month|past month|last month|30 days', q):
        return 30
    if re.search(r'semester|so far|overall|all time|ever', q):
        return 365
    return None


def _builtin(user, scope, question):
    q = question.lower().strip()
    course = None
    for a in scope.assigns:
        for key in (a.course.code, a.course.name, _initials(a.course.name)):
            if key and len(key) >= 2 and re.search(r'\b%s\b' % re.escape(key.lower()), q):
                course = a.course.name if key != a.course.code else a.course.code
                break
        if course:
            break
    cls = next((c.class_name for c in scope.classes()
                if re.sub(r'[^a-z0-9]', '', c.class_name.lower()) in re.sub(r'[^a-z0-9]', '', q)), None)
    threshold = settings.ATTENDANCE_THRESHOLD

    # A student's own questions.
    if user.is_student or re.search(r'\b(my|me|i)\b', q) and user.is_student:
        t = student_attendance(scope)
        if 'error' in t:
            return {'answer': t['error'], 'tables': []}
        lost = [r for r in t['rows'] if r[4].startswith("Can't")]
        msg = "You're at %s%% overall%s." % (t['overall_now'], '' if t['overall_projected'] is None else
                                             ', heading for about %s%% by the end of the semester' % t['overall_projected'])
        if re.search(r'miss|skip|bunk|leave', q):
            options = [r for r in t['rows'] if isinstance(r[5], int)]
            if options:
                msg += ' You can still miss: ' + ', '.join('%s %d' % (r[0], r[5]) for r in options[:5]) + '.'
        if lost:
            msg += ' %d%% is out of reach in %s; talk to your class teacher.' % (threshold, ', '.join(r[0] for r in lost))
        return {'answer': msg, 'tables': [t]}

    # Someone specific.
    m = re.search(r"(?:how is|how's|attendance (?:of|for)|about|details? (?:of|for)|show me)\s+([a-z][a-z ]+?)(?:'s|\s+doing|\?|$)", q)
    if m and not re.search(r'\b(class|classes|students|teachers|course)\b', m.group(1)):
        t = student_attendance(scope, m.group(1))
        if 'error' not in t:
            return {'answer': '%s is at %s%% overall%s.' % (
                t['student'], t['overall_now'], '' if t['overall_projected'] is None else
                ' and heading for about %s%% by the end of the semester' % t['overall_projected']), 'tables': [t]}

    if re.search(r'forecast|early warning|predict|projected|will (drop|slip|fall|go)|(on|off) (course|track)|'
                 r'going to (drop|fall|slip)|heading (for|below|under)|at risk of (dropping|falling)|'
                 r'(drop|fall|slip)(ping)? (below|under)|end of (the )?semester', q):
        t = early_warnings(scope)
        return {'answer': '%s forecast to finish below %d%% or unable to reach it.' % (
            _count(t['count'], 'student is', 'students are'), threshold) if t['count'] else
            'Nobody is forecast to drop below %d%%.' % threshold, 'tables': [t] if t['count'] else []}

    if re.search(r"mark|record|unmarked|pending|forgot|haven'?t (taken|marked)", q) and not user.is_student:
        t = teacher_marking(scope)
        behind = [r for r in t['rows'] if r[1] or r[2]]
        more = ' and %d more' % (len(behind) - 4) if len(behind) > 4 else ''
        return {'answer': ('%s behind on attendance: %s%s.' % (_count(len(behind), 'teacher is', 'teachers are'),
                                                                  ', '.join('%s (%d unmarked, %d not recorded)' % tuple(r) for r in behind[:4]), more))
                if behind else 'Everyone is up to date with attendance.', 'tables': [t]}

    m = re.search(r'(?:missed|absent (?:for|from)?|skipped|bunked)\s+(?:more than|over|at least|\>=?)?\s*' + _NUM, q) or \
        re.search(_NUM + r'\s*\+?\s*(?:or more\s+)?(?:lectures?|classes|times)', q) if re.search(r'miss|absent|skip|bunk', q) else None
    if m or re.search(r'\b(missed|absent|absences|skipped|bunked)\b', q):
        n = int(m.group(1)) if m else 1
        if m and re.search(r'more than|over', q):
            n += 1
        days = _days_in(q) or 30
        t = absences(scope, course=course, class_name=cls, since_days=days, min_absences=n)
        return {'answer': '%s missed %d or more%s lectures in the last %d days%s.' % (
            _count(len({r[0] for r in t['rows']}), 'student', 'students'), n,
            ' %s' % course if course else '', days, ' in %s' % cls if cls else '') if t['count'] else
            'Nobody missed %d or more%s lectures in the last %d days.' % (n, ' %s' % course if course else '', days),
            'tables': [t] if t['count'] else []}

    m = re.search(r'(?:below|under|less than|lower than|<)\s*' + _NUM, q)
    m2 = re.search(r'(?:above|over|more than|at least|>)\s*' + _NUM, q)
    if m or m2 or re.search(r'defaulter|short(age)?|at risk|low attendance|below the', q):
        below = int(m.group(1)) if m else (None if m2 else threshold)
        above = int(m2.group(1)) if m2 and not m else None
        t = find_students(scope, below_percent=below, above_percent=above, class_name=cls, course=course)
        return {'answer': '%s %s%s%s.' % (
            _count(t['count'], 'student is', 'students are'),
            'below %d%%' % below if below is not None else 'at or above %d%%' % above,
            ' in %s' % course if course else '', ' (%s)' % cls if cls else ''), 'tables': [t] if t['count'] else []}

    if re.search(r'\bclass(es)?\b', q) and re.search(r'lowest|highest|best|worst|compare|which|rank|summary|overview', q):
        t = class_summary(scope)
        if t['rows']:
            low, high = t['rows'][0], t['rows'][-1]
            return {'answer': '%s has the lowest attendance (%s%%) and %s the highest (%s%%).' % (low[0], low[2], high[0], high[2])
                    if len(t['rows']) > 1 else '%s is at %s%%.' % (low[0], low[2]), 'tables': [t]}

    if re.search(r'lectures?|log|held|taken|took', q):
        days = _days_in(q) or 14
        t = lecture_log(scope, course=course, class_name=cls, since_days=days)
        return {'answer': '%s held in the last %d days%s%s.' % (
            _count(t['count'], 'lecture was', 'lectures were'), days, ' for %s' % course if course else '',
            ' in %s' % cls if cls else ''), 'tables': [t] if t['count'] else []}

    if course or cls:
        t = find_students(scope, class_name=cls, course=course)
        return {'answer': 'Attendance%s%s, lowest first.' % (' in %s' % course if course else '', ' for %s' % cls if cls else ''),
                'tables': [t] if t['count'] else []}

    return {'answer': "I can answer questions like: who is below 75%, who missed 3+ CN lectures this month, "
                      "which class has the lowest attendance, who is on course to drop below 75%, "
                      "who hasn't marked attendance, or how a particular student is doing.", 'tables': []}


def _count(n, one, many):
    return '%d %s' % (n, one if n == 1 else many)


def suggestions(user):
    if user.is_student:
        return ['How many lectures can I still miss?', "What's my attendance forecast?", 'Which course am I worst in?']
    base = ['Who missed 3+ lectures this month?', 'Who is below 75%?', 'Who is on course to drop below 75%?']
    if user.can_manage_students:
        return base + ['Which class has the lowest attendance?', "Who hasn't marked attendance?"]
    return base + ['Lectures I took this week']


def answer(user, question, history=()):
    question = (question or '').strip()[:500]
    scope = Scope(user)
    if not question:
        return {'answer': 'Ask me something about attendance.', 'tables': [], 'source': 'builtin'}
    if ai.enabled():
        try:
            out = _claude(user, scope, question, list(history))
            out['source'] = 'claude'
            return out
        except ai.AIError as e:
            notice = str(e)
        except Exception as e:      # network/API failure: fall back rather than error the page
            log.warning('Ask SAS fell back to the built-in parser: %s', e)
            notice = 'Claude could not be reached, so the built-in assistant answered.'
        out = _builtin(user, scope, question)
        out.update(source='builtin', notice=notice)
        return out
    out = _builtin(user, scope, question)
    out['source'] = 'builtin'
    return out
