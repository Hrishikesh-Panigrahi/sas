"""Turns attendance facts into a written analysis.

`analyze()` asks Claude when AI_TOKEN is set (results are cached until the
facts change) and otherwise uses the built-in analyst below, which writes the
same shape of answer from the same facts:

    {headline, summary, insights: [{title, detail, tone}], actions: [{title, detail}]}

tone is one of: positive, neutral, warning, critical.
"""
import hashlib
import json

from django.conf import settings
from django.utils import timezone

from sas import ai
from .models import AIInsight

SCHEMA = {
    'type': 'object',
    'properties': {
        'headline': {'type': 'string'},
        'summary': {'type': 'string'},
        'insights': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'detail': {'type': 'string'},
                'tone': {'type': 'string', 'enum': ['positive', 'neutral', 'warning', 'critical']},
            },
            'required': ['title', 'detail', 'tone'],
            'additionalProperties': False,
        }},
        'actions': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'title': {'type': 'string'}, 'detail': {'type': 'string'}},
            'required': ['title', 'detail'],
            'additionalProperties': False,
        }},
    },
    'required': ['headline', 'summary', 'insights', 'actions'],
    'additionalProperties': False,
}

AUDIENCES = {
    'student': 'the student themself. Write in the second person ("you"), warm and '
               'encouraging but honest about risk.',
    'staff_student': 'a teacher or head of department looking at one student. Refer to the '
                     'student by first name and they/them pronouns.',
    'teacher': 'a teacher reviewing attendance in the courses they teach. Be practical and '
               'name specific students and courses.',
    'department': 'a head of department overseeing every class, course and teacher. Prioritise '
                  'what needs their decision or follow-up.',
}

SYSTEM = """You are the attendance analyst inside SAS, a college attendance system. You receive \
a JSON object of attendance facts computed by the app and write a short analysis for {audience}

The college requires {threshold}% attendance. Percentages are of lectures attended. \
"recent_change" compares the last two weeks with the four weeks before; "trailing" counts \
lectures missed in a row up to the latest one; "slots" counts timetabled lectures in the last \
two weeks and how many had no attendance recorded. Absences covered by approved leave are already \
left out of every percentage. "forecast" (one student) and "warnings" (many) project attendance to \
the end of the semester at the recent pace: "projected" is the likely final percentage, "best" the \
percentage if every remaining lecture is attended, "can_miss" how many remaining lectures can still \
be missed, "crosses_in_weeks" when the student would dip below the requirement; status "lost" \
means the requirement can no longer be reached and "slipping" means above it now but heading below.

Rules:
- Use only the numbers in the facts. Never invent students, courses or figures.
- headline: one line, under 12 words. summary: two or three sentences.
- insights: three to five, most important first, each a specific observation with its numbers. \
tone is critical for urgent risk, warning for things to watch, positive for good news, neutral \
otherwise.
- actions: two to four concrete next steps the reader can take this week.
- Plain text only, no markdown."""


def fingerprint(facts):
    return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()


def analyze(kind, facts, user, subject_id=None, refresh=False):
    """Return the analysis dict plus `source`, `generated_at` and maybe `notice`."""
    if ai.enabled():
        fp = fingerprint(facts)
        cached = AIInsight.objects.filter(user=user, kind=kind, subject_id=subject_id).first()
        if cached and cached.fingerprint == fp and not refresh:
            return cached.payload
        try:
            result = ai.ask_json(
                SYSTEM.format(audience=AUDIENCES[kind], threshold=settings.ATTENDANCE_THRESHOLD),
                json.dumps(facts, default=str), SCHEMA, effort='medium')
        except ai.AIError as e:
            result = builtin(kind, facts)
            result['notice'] = str(e)
            return result
        result.update(source='claude', model=settings.AI_MODEL,
                      generated_at=timezone.now().isoformat())
        AIInsight.objects.update_or_create(
            user=user, kind=kind, subject_id=subject_id,
            defaults={'fingerprint': fp, 'payload': result})
        return result
    return builtin(kind, facts)


def builtin(kind, facts):
    writer = {'student': _student, 'staff_student': _student,
              'teacher': _teacher, 'department': _department}[kind]
    result = writer(facts, kind) if kind in ('student', 'staff_student') else writer(facts)
    result.update(source='builtin', generated_at=timezone.now().isoformat())
    return result


# ------------------------------------------------------------------ helpers

def _pct(value):
    return '—' if value is None else '%d%%' % value


def _plural(n, word, plural=None):
    return '%d %s' % (n, word if n == 1 else (plural or word + 's'))


def _join(names):
    names = list(names)
    if len(names) <= 1:
        return ''.join(names)
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def _first(name):
    return (name or '').split(' ')[0]


def _insight(title, detail, tone='neutral'):
    return {'title': title, 'detail': detail, 'tone': tone}


def _action(title, detail):
    return {'title': title, 'detail': detail}


def _pattern_insights(facts, who):
    """Weekday / time-of-day weak spots, phrased for `who` ('your'/'their'/'')."""
    out = []
    overall = facts['overall']['percent']
    day, slot = facts.get('weak_day'), facts.get('weak_time')
    if day:
        out.append(_insight(
            '%ss are the weak spot' % day['label'],
            'Only %s of %s%s lectures are attended, against %s overall.'
            % (_pct(day['percent']), who, day['label'], _pct(overall)), 'warning'))
    if slot:
        out.append(_insight(
            '%s lectures are missed most' % slot['label'],
            'Attendance at the %s slot is %s, %d points below the overall %s.'
            % (slot['label'], _pct(slot['percent']), overall - slot['percent'], _pct(overall)),
            'warning'))
    return out


# ------------------------------------------------------------------ student

def _student(facts, kind):
    me = kind == 'student'
    name = _first(facts['first_name'])
    w = (dict(S='You', s='you', p='your', P='Your', be='are', have='have', obj='you') if me else
         dict(S=name, s=name, p='their', P='Their', be='is', have='has', obj='them'))
    o, t = facts['overall'], facts['threshold']
    pct = o['percent']

    if pct is None:
        return {'headline': 'No attendance recorded yet',
                'summary': "%s %s no marked lectures yet, so there's nothing to analyse. The analysis "
                           "will appear once teachers start marking attendance." % (w['S'], w['have']),
                'insights': [], 'actions': []}

    below = sorted((c for c in facts['courses'] if c['percent'] is not None and c['percent'] < t),
                   key=lambda c: c['percent'])
    if pct < 60:
        headline = 'Attendance is at serious risk (%s)' % _pct(pct)
    elif pct < t:
        headline = 'Below %d%% — %s in a row to recover' % (t, _plural(o['needed'], 'lecture'))
    elif pct < t + 5:
        headline = 'Just above %d%%, with little margin' % t
    elif below:
        headline = 'On track overall, but %s %s behind' % (_plural(len(below), 'course'),
                                                            'is' if len(below) == 1 else 'are')
    else:
        headline = 'Comfortably on track at %s' % _pct(pct)

    summary = '%s %s at %s overall (%d of %d lectures).' % (w['S'], w['be'], _pct(pct), o['present'], o['total'])
    fc = facts.get('forecast')
    lost = [c for c in fc['courses'] if c['status'] == 'lost'] if fc else []
    slipping = [c for c in fc['courses'] if c['status'] == 'slipping'] if fc else []
    change = facts['recent_change']
    if change and abs(change['delta']) >= 5:
        summary += ' Over the last two weeks it %s to %s, from %s before.' % (
            'rose' if change['delta'] > 0 else 'fell', _pct(change['recent']), _pct(change['before']))
    if below:
        summary += ' %s below %d%%: %s.' % (
            _plural(len(below), 'course is', 'courses are'), t,
            _join('%s (%s)' % (c['name'], _pct(c['percent'])) for c in below))
    elif pct >= t:
        summary += ' Every course is at or above the %d%% requirement.' % t
    if fc and fc['projected_overall'] is not None:
        summary += ' At the recent pace %s would finish the semester at about %s%s.' % (
            w['s'], _pct(fc['projected_overall']),
            '' if fc['projected_overall'] >= t else ' (attending everything left gets %s to %s)'
            % (w['obj'], _pct(fc['best_overall'])))

    insights = []
    for c in lost[:2]:
        insights.append(_insight(
            '%d%% is out of reach in %s' % (t, c['name']),
            'Even attending all %d remaining lectures would only reach %s. %s' % (
                c['remaining'], _pct(c['best']),
                'Talk to your class teacher now about options such as medical leave.' if me else
                'Worth a conversation about leave or condonation before exams.'),
            'critical'))
    for c in slipping[:2]:
        insights.append(_insight(
            'Heading below %d%% in %s' % (t, c['name']),
            '%s now, but at the recent pace about %s by the end%s. %s' % (
                _pct(c['current']), _pct(c['projected']),
                ', dipping under %d%% within %s' % (t, _plural(c['crosses_in_weeks'], 'week'))
                if c['crosses_in_weeks'] else '',
                ('%s can miss at most %d of the %d remaining lectures.' % (w['S'], c['can_miss'], c['remaining']))
                if c['can_miss'] is not None else ''),
            'warning'))
    if facts['trailing_absences'] >= 3:
        insights.append(_insight(
            'Missed the last %d lectures in a row' % facts['trailing_absences'],
            "%s %s missed every lecture since the last one %s attended. A run like this is the "
            "fastest way to fall below %d%%." % (w['S'], w['have'], w['s'], t), 'critical'))
    lost_names = {c['name'] for c in lost}
    for c in [c for c in below if c['name'] not in lost_names][:2]:
        insights.append(_insight(
            '%s needs attention' % c['name'],
            '%d of %d lectures attended (%s). Attending the next %s brings it back to %d%%.'
            % (c['present'], c['total'], _pct(c['percent']), _plural(c['needed'], 'lecture'), t),
            'critical' if c['percent'] < 60 else 'warning'))
    if change and change['delta'] <= -8:
        insights.append(_insight(
            'Attendance has slipped recently',
            '%s over the last two weeks, down from %s in the four weeks before.'
            % (_pct(change['recent']), _pct(change['before'])), 'warning'))
    elif change and change['delta'] >= 8:
        insights.append(_insight(
            'Improving lately',
            'Up to %s over the last two weeks from %s before. Keep it going.'
            % (_pct(change['recent']), _pct(change['before'])), 'positive'))
    insights += _pattern_insights(facts, w['p'] + ' ')
    avg = facts['class_average']
    if avg is not None and pct <= avg - 10:
        insights.append(_insight(
            '%d points below the class average' % (avg - pct),
            'The class averages %s; %s %s at %s.' % (_pct(avg), w['s'], w['be'], _pct(pct)), 'warning'))
    elif avg is not None and pct >= avg + 5:
        insights.append(_insight(
            'Ahead of the class',
            '%s %s %d points above the class average of %s.' % (w['S'], w['be'], pct - avg, _pct(avg)),
            'positive'))
    best = max(facts['courses'], key=lambda c: (c['percent'] or 0, c['total']))
    if best['percent'] is not None and best['percent'] >= 90 and len(insights) < 5:
        insights.append(_insight(
            'Strongest in %s' % best['name'],
            '%d of %d lectures attended (%s).' % (best['present'], best['total'], _pct(best['percent'])),
            'positive'))

    actions = []
    if lost:
        actions.append(_action(
            'Talk to your class teacher about %s' % lost[0]['name'] if me else 'Discuss options with %s' % name,
            'The %d%% mark can no longer be reached by attendance alone, so it needs a plan now, not at exam time.' % t))
    if slipping and slipping[0]['can_miss'] is not None:
        c = slipping[0]
        actions.append(_action(
            'Protect %s' % c['name'],
            '%s can miss at most %d more of its %d remaining lectures and still finish at %d%%.'
            % (w['S'], c['can_miss'], c['remaining'], t)))
    recoverable = [c for c in below if c['name'] not in lost_names]
    if recoverable:
        c = recoverable[0]
        actions.append(_action(
            'Prioritise %s' % c['name'],
            '%s every %s lecture for the next %s; that alone lifts it to %d%%.'
            % ('Attend' if me else 'Encourage them to attend', c['name'], _plural(c['needed'], 'session'), t)))
    if facts['trailing_absences'] >= 3:
        actions.append(_action(
            'Talk to your class teacher' if me else 'Check in with %s' % name,
            'If something is keeping you away, letting them know early helps.' if me else
            '%s %s missed %d lectures in a row; a quick conversation now can stop the slide.'
            % (name, w['have'], facts['trailing_absences'])))
    if facts.get('weak_day'):
        actions.append(_action(
            'Plan around %ss' % facts['weak_day']['label'],
            'Most missed lectures fall on %ss. %s.' % (
                facts['weak_day']['label'],
                'Set a reminder the night before' if me else 'Ask what makes that day hard')))
    if not actions:
        actions.append(_action(
            'Keep the streak going' if me else 'Acknowledge the good record',
            'Nothing needs fixing right now. Staying above %d%% in every course keeps exam eligibility '
            'safe.' % t if me else '%s is in good standing; a word of recognition goes a long way.' % name))
    return {'headline': headline, 'summary': summary, 'insights': insights[:5], 'actions': actions[:4]}


# ------------------------------------------------------------------ teacher

def _teacher(facts):
    t = facts['threshold']
    courses = [c for c in facts['courses'] if c['total']]
    if not facts['courses']:
        return {'headline': 'No classes assigned yet',
                'summary': "You aren't the teacher of any course in a class yet, so there's nothing "
                           "to analyse.", 'insights': [], 'actions': []}
    if not courses:
        return {'headline': 'No attendance marked yet',
                'summary': "None of your %s has marked lectures yet. Once you take attendance, "
                           "trends and at-risk students show up here."
                           % _plural(len(facts['courses']), 'course'),
                'insights': [], 'actions': [_action('Take your first attendance',
                                                    'Open Attendance and start today\'s lecture.')]}

    overall = facts['overall']['percent']
    num_below = facts['students_below']
    streak_students = {s['name']: s for c in courses for s in c['streaks']}
    worst = min(courses, key=lambda c: c['percent'])

    if streak_students:
        headline = '%s need%s follow-up' % (_plural(len(streak_students), 'student'),
                                            's' if len(streak_students) == 1 else '')
    elif num_below:
        headline = '%s below %d%% across your classes' % (_plural(num_below, 'student'), t)
    else:
        headline = 'Attendance in your classes is healthy at %s' % _pct(overall)

    summary = 'Across %s you have marked %s; average attendance is %s.' % (
        _plural(len(facts['courses']), 'course'),
        _plural(sum(c['lectures'] for c in courses), 'lecture'), _pct(overall))
    change = facts['recent_change']
    if change and abs(change['delta']) >= 5:
        summary += ' It has %s to %s over the last two weeks.' % (
            'risen' if change['delta'] > 0 else 'dropped', _pct(change['recent']))
    pending = facts['unmarked'] + facts['missed_slots']
    if pending:
        summary += ' %s still %s attendance recorded.' % (
            _plural(pending, 'lecture'), 'needs' if pending == 1 else 'need')

    insights = []
    if streak_students:
        worst_streaks = sorted(streak_students.values(), key=lambda s: -s['trailing'])[:3]
        insights.append(_insight(
            '%s missed their last few lectures' % _join(s['name'] for s in worst_streaks),
            '; '.join('%s has missed %d in a row (%s overall)' % (_first(s['name']), s['trailing'],
                                                                  _pct(s['percent'])) for s in worst_streaks) + '.',
            'critical'))
    worst_listed = None
    if worst['percent'] < t or (len(courses) > 1 and worst['percent'] <= overall - 8):
        worst_listed = worst
        detail = '%s over %s.' % (_pct(worst['percent']), _plural(worst['lectures'], 'lecture'))
        if worst['change'] and abs(worst['change']['delta']) >= 5:
            detail += ' %s %d points in the last two weeks.' % (
                'Up' if worst['change']['delta'] > 0 else 'Down', abs(worst['change']['delta']))
        if worst['below']:
            detail += ' Lowest: %s.' % _join('%s (%s)' % (s['name'], _pct(s['percent']))
                                             for s in worst['below'][:3])
        insights.append(_insight('%s · %s averages %s' % (worst['course'], worst['class_name'],
                                                          _pct(worst['percent'])), detail,
                                 'warning' if worst['percent'] >= 60 else 'critical'))
    below_courses = [c for c in courses if c['below'] and c is not worst_listed]
    if below_courses:
        insights.append(_insight(
            '%s below %d%%' % (_plural(num_below, 'student'), t),
            ' '.join('%s · %s: %s.' % (c['course'], c['class_name'],
                                       _join('%s (%s)' % (s['name'], _pct(s['percent'])) for s in c['below'][:4]))
                     for c in below_courses[:2]),
            'warning'))
    warn = facts.get('warnings') or {}
    if warn.get('cannot_recover'):
        people = warn['cannot_recover_students'][:3]
        insights.append(_insight(
            '%s can no longer reach %d%%' % (_plural(warn['cannot_recover'], 'student'), t),
            ' '.join('%s in %s: at most %s even attending everything.' % (p['name'], p['course'], _pct(p['best']))
                     for p in people), 'critical'))
    if warn.get('will_slip'):
        people = warn['will_slip_students'][:3]
        insights.append(_insight(
            '%s will slip below %d%% at this pace' % (_plural(warn['will_slip'], 'student'), t),
            ' '.join('%s in %s: %s now, about %s by the end%s.' % (
                p['name'], p['course'], _pct(p['current']), _pct(p['projected']),
                ' (below %d%% in %s)' % (t, _plural(p['crosses_in_weeks'], 'week')) if p['crosses_in_weeks'] else '')
                for p in people), 'warning'))
    if facts['missed_slots']:
        gaps = [c for c in courses if c['slots']['missed']]
        insights.append(_insight(
            '%s on the timetable with no record' % _plural(facts['missed_slots'], 'lecture'),
            'In the last two weeks: %s. Either the lecture didn\'t happen or attendance wasn\'t taken.'
            % _join('%s · %s (%d)' % (c['course'], c['class_name'], c['slots']['missed']) for c in gaps),
            'warning'))
    if facts['unmarked']:
        insights.append(_insight(
            '%s waiting to be marked' % _plural(facts['unmarked'], 'lecture'),
            'These lectures were started but attendance was never saved, so they are left out of '
            'every percentage.', 'warning'))
    insights += _pattern_insights(facts, 'your ')
    best = max(courses, key=lambda c: c['percent'])
    if best is not worst and best['percent'] >= 85:
        insights.append(_insight('%s · %s is your strongest' % (best['course'], best['class_name']),
                                 '%s average attendance.' % _pct(best['percent']), 'positive'))

    actions = []
    if warn.get('will_slip'):
        names = [_first(p['name']) for p in warn['will_slip_students'][:3]]
        actions.append(_action('Warn %s early' % _join(names),
                               "They're above %d%% today but trending below it; a heads-up now costs less "
                               "than a shortage later." % t))
    if facts['unmarked']:
        actions.append(_action('Mark the %s' % _plural(facts['unmarked'], 'pending lecture'),
                               'They are listed under "Waiting to be marked" on your dashboard.'))
    if streak_students:
        names = sorted(streak_students.values(), key=lambda s: -s['trailing'])[:3]
        actions.append(_action('Follow up with %s' % _join(_first(s['name']) for s in names),
                               'A short check-in or a note to their class teacher before the gap '
                               'widens.'))
    elif num_below:
        names = sorted((s for c in courses for s in c['below']), key=lambda s: s['percent'])
        unique = list(dict.fromkeys(_first(s['name']) for s in names))[:3]
        actions.append(_action('Check in with %s' % _join(unique),
                               'They are below %d%% in your courses; a word now is easier than a '
                               'shortage notice later.' % t))
    if facts['missed_slots']:
        actions.append(_action('Fill in missed lectures',
                               'If those timetabled lectures took place, add them from the course\'s '
                               'attendance page with the right date.'))
    if facts.get('weak_time'):
        actions.append(_action('Rethink the %s slot' % facts['weak_time']['label'],
                               'Starting with a short recap or quiz rewards turning up on time.'))
    if not actions:
        actions.append(_action('Keep it up', 'Attendance is healthy and up to date in every course.'))
    return {'headline': headline, 'summary': summary, 'insights': insights[:5], 'actions': actions[:4]}


# ------------------------------------------------------------------ department

def _department(facts):
    t = facts['threshold']
    overall = facts['overall']['percent']
    risk = facts['at_risk']
    gaps = facts['gaps']
    if overall is None:
        insights = []
        if gaps['classes_without_timetable']:
            insights.append(_insight('No timetable yet',
                                     '%s %s no timetable.' % (_join(gaps['classes_without_timetable']),
                                                              'has' if len(gaps['classes_without_timetable']) == 1 else 'have')))
        return {'headline': 'No attendance recorded yet',
                'summary': 'Once teachers start marking lectures, department-wide trends appear here.',
                'insights': insights, 'actions': []}

    headline = 'Department attendance at %s' % _pct(overall)
    if risk['count']:
        headline += ' — %s below %d%%' % (_plural(risk['count'], 'student'), t)

    classes = [c for c in facts['classes'] if c['total']]
    summary = '%s attended across %s over %s.' % (
        _pct(overall), _plural(len(classes), 'class', 'classes'),
        _plural(facts['overall']['total'], 'student-lecture'))
    change = facts['recent_change']
    if change and abs(change['delta']) >= 3:
        summary += ' Over the last two weeks it %s to %s, from %s in the weeks before.' % (
            'rose' if change['delta'] > 0 else 'slipped', _pct(change['recent']),
            _pct(change['before']))
    lagging = [t_ for t_ in facts['teachers'] if t_['unmarked'] + t_['missed_slots'] >= 2]
    if lagging:
        summary += ' %s behind on marking attendance.' % (
            _plural(len(lagging), 'teacher is', 'teachers are'))

    insights = []
    if risk['count']:
        insights.append(_insight(
            '%s below %d%%' % (_plural(risk['count'], 'student'), t),
            '%s%sLowest: %s.' % (
                ('%d of them %s under 60%%. ' % (risk['critical'], 'is' if risk['critical'] == 1 else 'are'))
                if risk['critical'] else '',
                '' if not risk['streaks'] else '%s %s missed 4+ lectures in a row. ' % (
                    _join(s['name'] for s in risk['streaks'][:3]),
                    'has' if len(risk['streaks'][:3]) == 1 else 'have'),
                _join('%s, %s (%s)' % (s['name'], s['class'], _pct(s['percent'])) for s in risk['students'][:3])),
            'critical' if risk['critical'] else 'warning'))
    warn = facts.get('warnings') or {}
    if warn.get('cannot_recover') or warn.get('will_slip'):
        parts = []
        if warn.get('cannot_recover'):
            parts.append('%s can no longer reach %d%% in at least one course (%s).' % (
                _plural(warn['cannot_recover'], 'student'), t,
                _join('%s in %s' % (p['name'], p['course']) for p in warn['cannot_recover_students'][:2])))
        if warn.get('will_slip'):
            parts.append('%s %s above %d%% now but on course to finish below it (%s).' % (
                _plural(warn['will_slip'], 'student'), 'is' if warn['will_slip'] == 1 else 'are', t,
                _join('%s in %s' % (p['name'], p['course']) for p in warn['will_slip_students'][:2])))
        insights.append(_insight('Early warnings for the rest of the semester', ' '.join(parts),
                                 'critical' if warn.get('cannot_recover') else 'warning'))
    if len(classes) > 1:
        low = min(classes, key=lambda c: c['percent'])
        high = max(classes, key=lambda c: c['percent'])
        if high['percent'] - low['percent'] >= 5:
            detail = '%s against %s in %s.' % (_pct(low['percent']), _pct(high['percent']), high['name'])
            if low['change'] and abs(low['change']['delta']) >= 5:
                detail += ' It moved %+d points in the last two weeks.' % low['change']['delta']
            insights.append(_insight('%s trails the department' % low['name'], detail,
                                     'warning' if low['percent'] < t + 5 else 'neutral'))
    if facts['lowest_courses']:
        c = facts['lowest_courses'][0]
        if c['percent'] < t:
            insights.append(_insight(
                '%s · %s is the lowest course' % (c['course'], c['class_name']),
                '%s attendance, taught by %s.' % (_pct(c['percent']), c['teacher']),
                'warning'))
    if lagging:
        insights.append(_insight(
            'Attendance records are incomplete',
            _join('%s (%s)' % (t_['name'], ', '.join(filter(None, [
                _plural(t_['unmarked'], 'unmarked lecture') if t_['unmarked'] else '',
                _plural(t_['missed_slots'], 'timetabled lecture') + ' not recorded' if t_['missed_slots'] else '',
            ]))) for t_ in lagging[:3]) + '. Percentages for their classes may be overstated.',
            'warning'))
    insights += _pattern_insights(facts, '')
    setup = []
    if gaps['classes_without_timetable']:
        setup.append('%s %s no timetable' % (_join(gaps['classes_without_timetable']),
                                             'has' if len(gaps['classes_without_timetable']) == 1 else 'have'))
    if gaps['idle_teachers']:
        setup.append('%s %s not teaching any course' % (_join(gaps['idle_teachers']),
                                                       'is' if len(gaps['idle_teachers']) == 1 else 'are'))
    if gaps['students_without_class']:
        setup.append('%s %s not in a class' % (_plural(gaps['students_without_class'], 'student'),
                                               'is' if gaps['students_without_class'] == 1 else 'are'))
    if setup:
        text = '; '.join(setup)
        insights.append(_insight('Setup gaps', text[0].upper() + text[1:] + '.', 'neutral'))
    if facts['highest_courses'] and len(insights) < 6:
        c = facts['highest_courses'][0]
        if c['percent'] >= 85:
            insights.append(_insight('%s · %s leads with %s' % (c['course'], c['class_name'], _pct(c['percent'])),
                                     'Taught by %s.' % c['teacher'], 'positive'))

    actions = []
    if risk['critical']:
        actions.append(_action('Meet the %s under 60%%' % _plural(risk['critical'], 'student'),
                               'They risk losing exam eligibility; involve class teachers and parents early.'))
    elif risk['count']:
        actions.append(_action('Ask class teachers to contact at-risk students',
                               '%s %s below %d%%; a list is in the at-risk table below.'
                               % (_plural(risk['count'], 'student'), 'is' if risk['count'] == 1 else 'are', t)))
    if warn.get('will_slip'):
        actions.append(_action('Send early warnings to %s' % _plural(warn['will_slip'], 'student'),
                               'They are still above %d%%, so a nudge now can keep them there.' % t))
    if lagging:
        actions.append(_action('Remind %s to mark attendance' % _join(_first(t_['name']) for t_ in lagging[:3]),
                               'Unmarked and unrecorded lectures distort every report.'))
    if gaps['classes_without_timetable']:
        actions.append(_action('Generate a timetable for %s' % gaps['classes_without_timetable'][0],
                               'The timetable generator builds a clash-free week in seconds.'))
    if gaps['idle_teachers']:
        actions.append(_action('Give %s a course' % _join(gaps['idle_teachers'][:2]),
                               'Assign them from a class\'s edit page.'))
    if not actions:
        actions.append(_action('No action needed', 'Attendance and records are in good shape.'))
    return {'headline': headline, 'summary': summary, 'insights': insights[:6], 'actions': actions[:4]}
