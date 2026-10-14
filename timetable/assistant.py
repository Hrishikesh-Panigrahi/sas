"""Turns plain-English timetable requests into generator rules.

    parse("Meera can't teach on Friday afternoons; keep Wednesday after lunch free", context)

`context` lists the class's teachers, courses, days and periods. Claude does the
parsing when AI_TOKEN is set; otherwise the built-in parser below handles the
common phrasings. Both return the same shape:

    {understood: [str], unrecognized: [str], source,
     teacher_unavailable: [{teacher_id, day, start, end}],
     class_blocked: [{day, start, end}],
     avoid_days: [{course_id, days}], preferred_time: [{course_id, time}],
     lectures_per_week: [{course_id, count}],
     max_periods_per_day: int (0 = unchanged), max_consecutive: int (0 = unchanged),
     avoid_first_period / avoid_last_period: "yes" | "no" | "unchanged"}
"""
import json
import re

from sas import ai

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
_DAY_ALIASES = {
    'Monday': ['monday', 'mon'], 'Tuesday': ['tuesday', 'tues', 'tue'],
    'Wednesday': ['wednesday', 'wed'], 'Thursday': ['thursday', 'thurs', 'thur', 'thu'],
    'Friday': ['friday', 'fri'], 'Saturday': ['saturday', 'sat'], 'Sunday': ['sunday', 'sun'],
}

_block = {'type': 'object', 'properties': {
    'day': {'type': 'string'}, 'start': {'type': 'string'}, 'end': {'type': 'string'}},
    'required': ['day', 'start', 'end'], 'additionalProperties': False}

SCHEMA = {
    'type': 'object',
    'properties': {
        'understood': {'type': 'array', 'items': {'type': 'string'}},
        'unrecognized': {'type': 'array', 'items': {'type': 'string'}},
        'teacher_unavailable': {'type': 'array', 'items': {
            'type': 'object', 'properties': {
                'teacher_id': {'type': 'integer'}, 'day': {'type': 'string'},
                'start': {'type': 'string'}, 'end': {'type': 'string'}},
            'required': ['teacher_id', 'day', 'start', 'end'], 'additionalProperties': False}},
        'class_blocked': {'type': 'array', 'items': _block},
        'avoid_days': {'type': 'array', 'items': {
            'type': 'object', 'properties': {
                'course_id': {'type': 'integer'}, 'days': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['course_id', 'days'], 'additionalProperties': False}},
        'preferred_time': {'type': 'array', 'items': {
            'type': 'object', 'properties': {
                'course_id': {'type': 'integer'},
                'time': {'type': 'string', 'enum': ['morning', 'afternoon']}},
            'required': ['course_id', 'time'], 'additionalProperties': False}},
        'lectures_per_week': {'type': 'array', 'items': {
            'type': 'object', 'properties': {
                'course_id': {'type': 'integer'}, 'count': {'type': 'integer'}},
            'required': ['course_id', 'count'], 'additionalProperties': False}},
        'max_periods_per_day': {'type': 'integer'},
        'max_consecutive': {'type': 'integer'},
        'avoid_first_period': {'type': 'string', 'enum': ['yes', 'no', 'unchanged']},
        'avoid_last_period': {'type': 'string', 'enum': ['yes', 'no', 'unchanged']},
    },
    'required': ['understood', 'unrecognized', 'teacher_unavailable', 'class_blocked', 'avoid_days',
                 'preferred_time', 'lectures_per_week', 'max_periods_per_day', 'max_consecutive',
                 'avoid_first_period', 'avoid_last_period'],
    'additionalProperties': False,
}

SYSTEM = """You convert a college timetable planner's plain-English requests into scheduling rules \
for a timetable generator. The user message is JSON with "request" (the planner's text) and \
"context" (the class's days, periods, teachers and courses, with ids).

Rules:
- Use only teacher_id and course_id values from the context. Days must be full names from \
context.days. Times are 24-hour "HH:MM" and should line up with period boundaries.
- "Morning" means from the first period until 12:15; "afternoon" means from 14:00 to the end \
of the last period. A whole day is the first period's start to the last period's end.
- teacher_unavailable: times a teacher cannot teach. class_blocked: times the whole class must \
be free (sports, assembly, a free afternoon). avoid_days: soft preference to keep a course off \
those days. preferred_time: soft preference for a course's lectures.
- Use 0 for max_periods_per_day / max_consecutive and "unchanged" for the first/last period \
flags when the request doesn't mention them.
- understood: one short sentence per rule you produced, naming people and courses.
- unrecognized: any part of the request you could not turn into a rule, quoted briefly."""


def parse(text, context):
    text = (text or '').strip()
    if not text:
        return _empty(source='builtin')
    if ai.enabled():
        try:
            result = ai.ask_json(SYSTEM, json.dumps({'request': text, 'context': context}),
                                 SCHEMA, effort='low')
            return _clean(result, context, source='claude')
        except ai.AIError as e:
            result = builtin(text, context)
            result['notice'] = str(e)
            return result
    return builtin(text, context)


def _empty(source):
    return {'understood': [], 'unrecognized': [], 'teacher_unavailable': [], 'class_blocked': [],
            'avoid_days': [], 'preferred_time': [], 'lectures_per_week': [],
            'max_periods_per_day': 0, 'max_consecutive': 0,
            'avoid_first_period': 'unchanged', 'avoid_last_period': 'unchanged', 'source': source}


def _clean(result, context, source):
    """Drop anything that doesn't refer to this class's teachers, courses or days."""
    teachers = {t['id'] for t in context['teachers']}
    courses = {c['id'] for c in context['courses']}
    days = set(context['days'])
    out = _empty(source)
    out.update(understood=result.get('understood', []), unrecognized=result.get('unrecognized', []))
    out['teacher_unavailable'] = [b for b in result.get('teacher_unavailable', [])
                                  if b['teacher_id'] in teachers and b['day'] in days and _times_ok(b)]
    out['class_blocked'] = [b for b in result.get('class_blocked', []) if b['day'] in days and _times_ok(b)]
    out['avoid_days'] = [{'course_id': a['course_id'], 'days': [d for d in a['days'] if d in days]}
                         for a in result.get('avoid_days', []) if a['course_id'] in courses]
    out['preferred_time'] = [p for p in result.get('preferred_time', []) if p['course_id'] in courses]
    out['lectures_per_week'] = [p for p in result.get('lectures_per_week', [])
                                if p['course_id'] in courses and 0 <= p['count'] <= 10]
    for key in ('max_periods_per_day', 'max_consecutive'):
        value = result.get(key) or 0
        out[key] = value if 0 <= value <= 12 else 0
    for key in ('avoid_first_period', 'avoid_last_period'):
        out[key] = result.get(key) if result.get(key) in ('yes', 'no') else 'unchanged'
    return out


def _times_ok(block):
    return bool(re.fullmatch(r'\d\d:\d\d', block['start']) and re.fullmatch(r'\d\d:\d\d', block['end'])
                and block['start'] < block['end'])


# ------------------------------------------------------------------ built-in parser

_NUMBERS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8}
_UNAVAILABLE = re.compile(r"\b(can'?t|cannot|can ?not|unavailable|not available|isn'?t available|"
                          r"busy|off|on leave|away|no teaching|doesn'?t teach|won'?t)\b")
_FREE = re.compile(r'\b(free|no (classes|lectures|lessons|sessions)|nothing|sports?|assembly|'
                   r'block(ed)?|keep .* clear|clear)\b')
_AVOID = re.compile(r'\b(avoid|not on|no\b|never|keep .* off|shouldn\'?t be on|move .* off)')


def _split(text):
    parts = re.split(r'[.;\n]+|\s+(?:and also|also)\s+', text)
    return [p.strip() for p in parts if p.strip()]


def _days(clause, context):
    c = clause.lower()
    if re.search(r'\b(every ?day|daily|all week|any day|each day|weekdays)\b', c):
        return list(context['days'])
    return [d for d in context['days'] if re.search(r'\b(%s)s?\b' % '|'.join(_DAY_ALIASES[d]), c)]


def _period_bounds(context):
    periods = context['periods']
    return periods[0]['start'], periods[-1]['end']


def _clock(h, m, ampm, context):
    h = int(h)
    m = int(m or 0)
    if ampm == 'pm' and h < 12:
        h += 12
    elif not ampm and h < 8:     # "after 3" in a college day means 15:00
        h += 12
    return '%02d:%02d' % (h, m)


def _time_range(clause, context):
    """Return (start, end) for the part of the day a clause mentions, or the whole day."""
    c = clause.lower()
    first, last = _period_bounds(context)
    t = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
    m = re.search(r'(?:from|between)\s+%s\s*(?:-|to|and|until|till)\s*%s' % (t, t), c)
    if m:
        return _clock(*m.group(1, 2, 3), context), _clock(*m.group(4, 5, 6), context)
    m = re.search(r'(?:after|from)\s+%s' % t, c)
    if m:
        return _clock(*m.group(1, 2, 3), context), last
    m = re.search(r'(?:before|until|till)\s+%s' % t, c)
    if m:
        return first, _clock(*m.group(1, 2, 3), context)
    if re.search(r'after lunch|afternoons?|post[- ]lunch|evening', c):
        return '14:00', last
    if re.search(r'mornings?|before lunch|first half', c):
        return first, '12:15'
    if re.search(r'first (period|lecture|slot|hour)', c):
        return first, context['periods'][0]['end']
    if re.search(r'last (period|lecture|slot|hour)', c):
        return context['periods'][-1]['start'], last
    return first, last


def _match_people(clause, items, keys):
    c = ' %s ' % re.sub(r'[^a-z0-9 ]', ' ', clause.lower())
    hits = []
    for item in items:
        for key in keys(item):
            if key and re.search(r'\b%s\b' % re.escape(key.lower()), c):
                hits.append(item)
                break
    return hits


def _teacher_keys(t):
    parts = t['name'].split()
    return [t['name']] + [p for p in parts if len(p) > 2]


def _course_keys(c):
    keys = [c['name'], c['code']]
    # Initialism, e.g. "Computer Networks" -> "cn", "Data Warehousing and Mining" -> "dwm".
    words = [w for w in re.findall(r'[A-Za-z]+', c['name']) if w.lower() not in ('and', 'of', 'the', 'lab')]
    if len(words) > 1:
        keys.append(''.join(w[0] for w in words))
    return keys


def builtin(text, context):
    out = _empty('builtin')
    def days_word(ds):
        if len(ds) == len(context['days']):
            return 'every day'
        return ds[0] if len(ds) == 1 else ', '.join(ds[:-1]) + ' and ' + ds[-1]

    for clause in _split(text):
        c = clause.lower()
        handled = False
        days = _days(clause, context)
        teachers = _match_people(clause, context['teachers'], _teacher_keys)
        courses = _match_people(clause, context['courses'], _course_keys)
        if len(courses) > 1:
            wants_lab = bool(re.search(r'\blabs?\b', c))
            preferred = [x for x in courses if ('lab' in x['name'].lower()) == wants_lab]
            courses = preferred or courses
        start, end = _time_range(clause, context)
        part = '' if (start, end) == _period_bounds(context) else ' %s–%s' % (start, end)

        n = re.search(r'(?:max(?:imum)?|at most|no more than|up to|only)\s+(\d+|%s)\s+'
                      r'(?:lectures?|periods?|hours?|classes|sessions?)\s+(?:a|per|each)\s+day'
                      % '|'.join(_NUMBERS), c)
        if n:
            value = int(_NUMBERS.get(n.group(1), n.group(1)))
            out['max_periods_per_day'] = value
            out['understood'].append('At most %d periods a day.' % value)
            handled = True

        n = re.search(r'(?:no more than|at most|max(?:imum)?|only)\s+(\d+|%s)\s+(?:\w+\s+)?'
                      r'(?:in a row|back[- ]to[- ]back|consecutive(?:ly)?)' % '|'.join(_NUMBERS), c)
        if n:
            value = int(_NUMBERS.get(n.group(1), n.group(1)))
            out['max_consecutive'] = value
            out['understood'].append('No more than %d periods in a row.' % value)
            handled = True

        if not teachers and not courses and re.search(r'first (period|lecture|slot)|9 ?am|early start', c) \
                and re.search(r'avoid|no |skip|without|late start|don\'?t', c) and not days:
            out['avoid_first_period'] = 'yes'
            out['understood'].append('Avoid the first period where possible.')
            handled = True
        if not teachers and not courses and re.search(r'last (period|lecture|slot)|finish early|late (classes|lectures)', c) \
                and re.search(r'avoid|no |skip|without|finish early|don\'?t', c) and not days:
            out['avoid_last_period'] = 'yes'
            out['understood'].append('Avoid the last period where possible.')
            handled = True

        for course in courses:
            m = re.search(r'(\d+|%s)\s+(?:times|lectures?|sessions?|classes)\s+(?:a|per|each)\s+week'
                          % '|'.join(_NUMBERS), c)
            if m:
                value = int(_NUMBERS.get(m.group(1), m.group(1)))
                out['lectures_per_week'].append({'course_id': course['id'], 'count': value})
                out['understood'].append('%s: %d lectures a week.' % (course['name'], value))
                handled = True

        if teachers and _UNAVAILABLE.search(c):
            target_days = days or list(context['days'])
            for t in teachers:
                for d in target_days:
                    out['teacher_unavailable'].append({'teacher_id': t['id'], 'day': d, 'start': start, 'end': end})
                out['understood'].append('%s is unavailable %s%s.' % (t['name'], days_word(target_days), part))
            handled = True
        elif courses and not handled and re.search(r'\b(morning|afternoon|after lunch|before lunch)s?\b', c) \
                and not _AVOID.search(c):
            when = 'afternoon' if re.search(r'afternoon|after lunch', c) else 'morning'
            for course in courses:
                out['preferred_time'].append({'course_id': course['id'], 'time': when})
                out['understood'].append('Prefer %s for %s.' % ('afternoons' if when == 'afternoon' else 'mornings',
                                                                course['name']))
            handled = True
        elif courses and days and _AVOID.search(c):
            for course in courses:
                out['avoid_days'].append({'course_id': course['id'], 'days': days})
                out['understood'].append('Keep %s off %s.' % (course['name'], days_word(days)))
            handled = True
        elif not teachers and not courses and days and _FREE.search(c):
            for d in days:
                out['class_blocked'].append({'day': d, 'start': start, 'end': end})
            out['understood'].append('Keep %s%s free for the class.' % (days_word(days), part))
            handled = True

        if not handled:
            out['unrecognized'].append(clause)
    return out
