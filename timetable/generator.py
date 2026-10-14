"""Builds a class's weekly timetable with the constraint solver.

The generator page edits a JSON *config* (week shape, how often each course
meets, rules); `generate()` turns it into solver sessions, adds the teachers'
commitments in other classes as hard constraints, and returns a JSON-friendly
result that `apply()` can save.
"""
import datetime
import math
import re
from collections import defaultdict

from django.db import transaction

from attendance.models import Assign_cls
from . import solver
from .models import TimeTable

ALL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
DEFAULT_DAYS = ALL_DAYS[:5]
DEFAULT_PERIODS = [('09:00', '10:00'), ('10:00', '11:00'), ('11:15', '12:15'), ('12:15', '13:15'),
                   ('14:00', '15:00'), ('15:00', '16:00'), ('16:00', '17:00')]
BATCHES = ['A', 'B', 'C']
TIME = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


class ConfigError(ValueError):
    pass


def is_lab(course):
    return bool(re.match(r'^[A-Z]{2}L\d', course.code.upper())) or 'lab' in course.name.lower()


def _t(value):
    return datetime.datetime.strptime(value, '%H:%M').time()


def _hm(value):
    return value.strftime('%H:%M')


def _assignments(cls):
    return list(cls.assign_cls_set.select_related('course', 'teacher__user').order_by('course__code', 'id'))


def context(cls):
    """What the assistant needs to resolve names in a plain-English request."""
    assigns = _assignments(cls)
    teachers = {a.teacher_id: a.teacher.user.full_name for a in assigns}
    return {
        'days': list(ALL_DAYS),
        'periods': [{'start': s, 'end': e} for s, e in DEFAULT_PERIODS],
        'teachers': [{'id': i, 'name': n} for i, n in sorted(teachers.items(), key=lambda kv: kv[1])],
        'courses': [{'id': a.course_id, 'name': a.course.name, 'code': a.course.code} for a in assigns],
    }


def default_config(cls):
    rows = []
    for a in _assignments(cls):
        lab = is_lab(a.course)
        rows.append({
            'assign_id': a.id, 'course_id': a.course_id, 'name': a.course.name, 'code': a.course.code,
            'teacher_id': a.teacher_id, 'teacher': a.teacher.user.full_name,
            'lectures': 0 if lab else (2 if a.course.is_elective else 3),
            'labs': 1 if lab else 0, 'lab_length': 2, 'batches': ['A', 'B'] if lab else [],
        })
    ctx = context(cls)
    return {
        'days': list(DEFAULT_DAYS),
        'periods': ctx['periods'],
        'courses': rows,
        'rules': {
            'max_periods_per_day': 0, 'max_consecutive': 3,
            'avoid_first_period': False, 'avoid_last_period': False,
            'teacher_unavailable': [], 'class_blocked': [], 'avoid_days': [], 'preferred_time': [],
        },
    }


def _int(value, low, high, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def clean_config(cls, data):
    """Validate a config posted by the page; raise ConfigError with a readable message."""
    if not isinstance(data, dict):
        raise ConfigError('The settings could not be read.')
    days = [d for d in ALL_DAYS if d in (data.get('days') or [])]
    if not days:
        raise ConfigError('Pick at least one working day.')

    periods = []
    for p in data.get('periods') or []:
        start, end = str(p.get('start', '')), str(p.get('end', ''))
        if not (TIME.match(start) and TIME.match(end)) or start >= end:
            raise ConfigError('Each period needs a start and an end time, e.g. 09:00 to 10:00.')
        periods.append({'start': start, 'end': end})
    periods.sort(key=lambda p: p['start'])
    if not periods:
        raise ConfigError('Add at least one period to the day.')
    for a, b in zip(periods, periods[1:]):
        if b['start'] < a['end']:
            raise ConfigError('Periods %s–%s and %s–%s overlap.' % (a['start'], a['end'], b['start'], b['end']))

    assigns = {a.id: a for a in _assignments(cls)}
    courses = []
    for row in data.get('courses') or []:
        a = assigns.get(_int(row.get('assign_id'), 0, 10 ** 12, 0))
        if a is None:
            continue
        batches = [b for b in BATCHES if b in (row.get('batches') or [])]
        courses.append({
            'assign_id': a.id, 'course_id': a.course_id, 'name': a.course.name, 'code': a.course.code,
            'teacher_id': a.teacher_id, 'teacher': a.teacher.user.full_name,
            'lectures': _int(row.get('lectures'), 0, 8, 0),
            'labs': _int(row.get('labs'), 0, 4, 0),
            'lab_length': _int(row.get('lab_length'), 1, 4, 2),
            'batches': batches,
        })
    if not any(c['lectures'] or c['labs'] for c in courses):
        raise ConfigError('Give at least one course some lectures or labs to schedule.')

    rules = data.get('rules') or {}
    teacher_ids = {c['teacher_id'] for c in courses}
    course_ids = {c['course_id'] for c in courses}

    def blocks(items, need_teacher=False):
        out = []
        for b in items or []:
            if b.get('day') in days and TIME.match(str(b.get('start', ''))) and TIME.match(str(b.get('end', ''))) \
                    and b['start'] < b['end'] and (not need_teacher or b.get('teacher_id') in teacher_ids):
                item = {'day': b['day'], 'start': b['start'], 'end': b['end']}
                if need_teacher:
                    item['teacher_id'] = b['teacher_id']
                out.append(item)
        return out

    clean_rules = {
        'max_periods_per_day': _int(rules.get('max_periods_per_day'), 0, len(periods), 0),
        'max_consecutive': _int(rules.get('max_consecutive'), 1, len(periods), 3),
        'avoid_first_period': bool(rules.get('avoid_first_period')),
        'avoid_last_period': bool(rules.get('avoid_last_period')),
        'teacher_unavailable': blocks(rules.get('teacher_unavailable'), need_teacher=True),
        'class_blocked': blocks(rules.get('class_blocked')),
        'avoid_days': [{'course_id': a['course_id'], 'days': [d for d in a.get('days', []) if d in days]}
                       for a in rules.get('avoid_days') or [] if a.get('course_id') in course_ids],
        'preferred_time': [{'course_id': p['course_id'], 'time': p['time']}
                           for p in rules.get('preferred_time') or []
                           if p.get('course_id') in course_ids and p.get('time') in ('morning', 'afternoon')],
    }
    return {'days': days, 'periods': periods, 'courses': courses, 'rules': clean_rules}


def other_commitments(cls, teacher_ids, days):
    """Times these teachers already teach in other classes, as solver blocks."""
    teaches = defaultdict(set)
    for cls_id, course_id, teacher_id in Assign_cls.objects.exclude(cls=cls) \
            .filter(teacher_id__in=teacher_ids).values_list('cls_id', 'course_id', 'teacher_id'):
        teaches[(cls_id, course_id)].add(teacher_id)
    busy = defaultdict(list)
    for slot in TimeTable.objects.exclude(cls=cls).filter(day__in=days):
        for t in teaches.get((slot.cls_id, slot.course_id), ()):
            busy[t].append(solver.Block(slot.day, slot.start_time, slot.end_time))
    return busy


def generate(cls, config, seed=0, time_budget=1.2):
    days = config['days']
    periods = [solver.Period(_t(p['start']), _t(p['end'])) for p in config['periods']]
    sessions, rows = [], {}
    for row in config['courses']:
        rows[row['assign_id']] = row
        for n in range(row['lectures']):
            sessions.append(solver.Session('%d-L%d' % (row['assign_id'], n + 1), row['course_id'],
                                           (row['teacher_id'],), 'Lecture', 'All', 1))
        for batch in row['batches'] or ['All']:
            for n in range(row['labs']):
                sessions.append(solver.Session('%d-%s-%d' % (row['assign_id'], batch, n + 1), row['course_id'],
                                               (row['teacher_id'],), 'Lab', batch, row['lab_length']))

    r = config['rules']
    teacher_ids = {row['teacher_id'] for row in config['courses']}
    busy = other_commitments(cls, teacher_ids, days)
    commitments = sum(len(v) for v in busy.values())
    for b in r['teacher_unavailable']:
        busy[b['teacher_id']].append(solver.Block(b['day'], _t(b['start']), _t(b['end'])))
    avoid = defaultdict(set)
    for a in r['avoid_days']:
        avoid[a['course_id']].update(a['days'])
    rules = solver.Rules(
        teacher_busy=dict(busy),
        class_blocked=[solver.Block(b['day'], _t(b['start']), _t(b['end'])) for b in r['class_blocked']],
        max_periods_per_day=r['max_periods_per_day'] or None,
        avoid_days=dict(avoid),
        preferred_time={p['course_id']: p['time'] for p in r['preferred_time']},
        max_consecutive=r['max_consecutive'],
        avoid_first_period=r['avoid_first_period'],
        avoid_last_period=r['avoid_last_period'],
    )
    result = solver.generate(days, periods, sessions, rules, seed=seed, time_budget=time_budget)

    by_key = {s.key: s for s in sessions}
    colours = {}
    for row in config['courses']:
        colours.setdefault(row['course_id'], len(colours) % 8)

    def describe(s):
        row = rows[int(s.key.split('-')[0])]
        return {'key': s.key, 'assign_id': row['assign_id'], 'course_id': s.course_id,
                'course': row['name'], 'code': row['code'], 'teacher': row['teacher'],
                'kind': s.kind, 'batch': s.batch, 'length': s.length, 'colour': colours[s.course_id]}

    slots = []
    for p in result.placements:
        item = describe(by_key[p.session_key])
        item.update(day=p.day, period=p.period, start=_hm(p.start), end=_hm(p.end))
        slots.append(item)
    slots.sort(key=lambda s: (days.index(s['day']), s['period'], s['batch']))
    unplaced = [dict(describe(by_key[key]), reason=reason) for key, reason in result.unplaced]

    return {
        'seed': seed,
        'slots': slots,
        'unplaced': unplaced,
        'score': round(result.score, 1),
        'breakdown': {k: round(v, 1) for k, v in result.breakdown.items() if v},
        'quality': _quality(result.score, len(sessions), len(unplaced)),
        'stats': _stats(days, slots, len(config['periods'])),
        'highlights': _highlights(days, slots, unplaced, result, len(sessions), commitments, config),
        'attempts': result.attempts,
    }


def _quality(score, sessions, unplaced):
    """0–100: 100 means every session placed with no soft-rule penalties."""
    if not sessions:
        return 0
    value = 100 * math.exp(-(score / sessions) / 15) - 12 * unplaced
    return max(0, min(100, round(value)))


def _stats(days, slots, num_periods):
    per_day = {}
    for day in days:
        lanes = defaultdict(set)
        for s in slots:
            if s['day'] == day:
                for p in range(s['period'], s['period'] + s['length']):
                    lanes[s['batch']].add(p)
        all_ = lanes.pop('All', set())
        per_day[day] = max([len(all_ | b) for b in lanes.values()] or [len(all_)])
    teachers = defaultdict(int)
    for s in slots:
        teachers[s['teacher']] += s['length']
    return {
        'per_day': [{'day': d, 'periods': per_day[d], 'capacity': num_periods} for d in days],
        'teachers': [{'name': n, 'periods': p} for n, p in sorted(teachers.items(), key=lambda kv: -kv[1])],
        'total_periods': sum(s['length'] for s in slots),
    }


def _free_periods(days, slots):
    """Periods inside the school day when nobody in the class has anything scheduled."""
    free = 0
    for day in days:
        busy = {p for s in slots if s['day'] == day for p in range(s['period'], s['period'] + s['length'])}
        if busy:
            free += sum(1 for p in range(min(busy), max(busy)) if p not in busy)
    return free


def _highlights(days, slots, unplaced, result, total, commitments, config):
    notes = []
    if not unplaced:
        notes.append('All %d sessions fit with no clashes for the class or its teachers.' % total)
    else:
        notes.append('%d of %d sessions could not be placed; see why below.' % (len(unplaced), total))
    if commitments:
        notes.append('Worked around %d lecture%s the same teachers give in other classes.'
                     % (commitments, '' if commitments == 1 else 's'))
    labs = [s for s in slots if s['kind'] == 'Lab' and s['batch'] != 'All']
    parallel = sum(1 for a in labs for b in labs if a['key'] < b['key'] and a['day'] == b['day']
                   and a['period'] == b['period'] and a['batch'] != b['batch'])
    if parallel:
        notes.append('Lab batches run side by side %d time%s, so no batch sits idle while another is in the lab.'
                     % (parallel, '' if parallel == 1 else 's'))
    repeats = result.breakdown.get('same_day_repeat', 0)
    notes.append('No course meets twice on the same day.' if not repeats else
                 'Some courses meet twice in a day because the week is tight.')
    gaps = _free_periods(days, slots)
    if gaps:
        notes.append('%d free period%s with nothing scheduled fall between lectures across the week.'
                     % (gaps, '' if gaps == 1 else 's'))
    else:
        notes.append('No free periods stranded between lectures.')
    r = config['rules']
    honoured = len(r['teacher_unavailable']) + len(r['class_blocked'])
    if honoured:
        notes.append('Honoured %d blocked time%s from your rules.' % (honoured, '' if honoured == 1 else 's'))
    soft = result.breakdown.get('avoid_day', 0) + result.breakdown.get('time_preference', 0)
    if r['avoid_days'] or r['preferred_time']:
        notes.append('Every course preference was met.' if not soft else
                     'A few course preferences could not be met without breaking a hard rule.')
    return notes


@transaction.atomic
def apply(cls, slots):
    """Replace the class's timetable with `slots` (from a stored generate() result)."""
    cls.timetable_set.all().delete()
    TimeTable.objects.bulk_create(
        TimeTable(cls=cls, course_id=s['course_id'], lec_type=s['kind'], batch=s['batch'], day=s['day'],
                  start_time=_t(s['start']), end_time=_t(s['end']))
        for s in slots)
    return len(slots)


def conflicts(cls, slots):
    """Clashes with other classes' current timetables (they may change after generating)."""
    teacher_of = dict(Assign_cls.objects.filter(pk__in={s['assign_id'] for s in slots})
                      .values_list('id', 'teacher_id'))
    busy = other_commitments(cls, set(teacher_of.values()), {s['day'] for s in slots})
    found = []
    for s in slots:
        start, end = _t(s['start']), _t(s['end'])
        for b in busy.get(teacher_of[s['assign_id']], []):
            if b.day == s['day'] and b.start < end and start < b.end:
                found.append('%s on %s %s–%s' % (s['course'], s['day'], s['start'], s['end']))
                break
    return found
