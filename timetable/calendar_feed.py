"""A user's weekly timetable as an iCalendar (RFC 5545) subscription feed.

Each timetable slot becomes one weekly recurring event that runs until the end
of the semester. Feeds are addressed by a signed token instead of a login, so
calendar apps can fetch them; anyone holding the link can read the timetable.
"""
import base64
import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import signing
from django.utils import timezone

from attendance.models import Assign_cls
from sas.semester import semester_end
from student.models import student
from .models import TimeTable

SALT = 'sas.calendar'
PRODID = '-//SAS//Student Attendance System//EN'
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
UTC = datetime.timezone.utc


# ---------- Tokens ----------

def make_token(user):
    """The secret, permanent token in a user's feed URL (URL-safe: A-Z a-z 0-9 - _)."""
    signed = signing.Signer(salt=SALT).sign(str(user.pk))
    return base64.urlsafe_b64encode(signed.encode()).decode('ascii').rstrip('=')


def user_pk_from_token(token):
    """The user id a token was made for, or None when it is not genuine."""
    try:
        padded = token + '=' * (-len(token) % 4)
        signed = base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8')
        return int(signing.Signer(salt=SALT).unsign(signed))
    except (ValueError, TypeError, signing.BadSignature):
        return None


# ---------- Which slots belong in a calendar ----------

def slots_for(user):
    """The timetable slots in a user's calendar, ordered by weekday and time.

    Teachers get every slot of each class + course they are assigned to;
    students get their class's slots for the whole class or their own lab batch.
    """
    slots = TimeTable.objects.filter(course__isnull=False).select_related('cls', 'course')
    if user.is_student:
        profile = student.objects.filter(user=user).first()
        if profile is None or profile.cls_id is None:
            return []
        batches = ['All', profile.batch] if profile.batch else ['All']
        result = list(slots.filter(cls_id=profile.cls_id, batch__in=batches))
    else:
        pairs = set(Assign_cls.objects.filter(teacher__user=user).values_list('cls_id', 'course_id'))
        if not pairs:
            return []
        result = [s for s in slots.filter(cls_id__in={c for c, _ in pairs})
                  if (s.cls_id, s.course_id) in pairs]
    day_index = {d: i for i, d in enumerate(WEEKDAYS)}
    result = [s for s in result if s.day in day_index]
    result.sort(key=lambda s: (day_index[s.day], s.start_time, s.cls.class_name, s.course.name))
    return result


def _teachers(slots):
    pairs = {(s.cls_id, s.course_id) for s in slots}
    teachers = {}
    if not pairs:
        return teachers
    assignments = (Assign_cls.objects
                   .filter(cls_id__in={c for c, _ in pairs}, course_id__in={k for _, k in pairs})
                   .select_related('teacher__user').order_by('teacher__user__first_name'))
    for a in assignments:
        if (a.cls_id, a.course_id) in pairs:
            u = a.teacher.user
            teachers.setdefault((a.cls_id, a.course_id), []).append(u.full_name or u.email)
    return teachers


def summary(slot):
    """'Networks', 'Networks · Lab', 'Networks · Lab, batch A'."""
    parts = []
    if slot.lec_type == 'Lab':
        parts.append('Lab')
    if slot.batch and slot.batch != 'All':
        parts.append('batch %s' % slot.batch)
    if not parts:
        return slot.course.name
    detail = ', '.join(parts)
    return '%s · %s' % (slot.course.name, detail[:1].upper() + detail[1:])


def events_for(user, today=None):
    """One dict per slot with everything a calendar event needs."""
    today = today or timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())
    slots = slots_for(user)
    teachers = _teachers(slots)
    events = []
    for slot in slots:
        date = monday + datetime.timedelta(days=WEEKDAYS.index(slot.day))
        names = teachers.get((slot.cls_id, slot.course_id), [])
        description = ['Course: %s (%s)' % (slot.course.name, slot.course.code),
                       'Class: %s' % slot.cls.class_name,
                       'Type: %s%s' % (slot.lec_type,
                                       '' if slot.batch == 'All' else ', batch %s' % slot.batch)]
        if names:
            description.append('%s: %s' % ('Teachers' if len(names) > 1 else 'Teacher', ', '.join(names)))
        events.append({
            'slot': slot,
            'uid': 'slot-%d@sas' % slot.id,
            'summary': summary(slot),
            'location': slot.cls.class_name,
            'description': '\n'.join(description),
            'teachers': names,
            'start': datetime.datetime.combine(date, slot.start_time),
            'end': datetime.datetime.combine(date, slot.end_time),
        })
    return events


# ---------- RFC 5545 formatting ----------

def escape_text(value):
    """Escape a TEXT value: backslash, semicolon, comma and newlines."""
    value = str(value).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,')
    return value.replace('\r\n', '\\n').replace('\r', '\\n').replace('\n', '\\n')


def fold(line):
    """Fold a content line so no physical line exceeds 75 octets (excluding CRLF).

    Continuation lines start with a single space; multi-byte UTF-8 characters
    are never split.
    """
    if len(line.encode('utf-8')) <= 75:
        return line
    parts, current, size, limit = [], [], 0, 75
    for ch in line:
        n = len(ch.encode('utf-8'))
        if size + n > limit:
            parts.append(''.join(current))
            current, size, limit = [], 0, 74   # the leading space takes one octet
        current.append(ch)
        size += n
    parts.append(''.join(current))
    return '\r\n '.join(parts)


def _local(dt):
    return dt.strftime('%Y%m%dT%H%M%S')


def _utc(dt):
    return dt.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')


def _offset(delta):
    seconds = int(delta.total_seconds())
    sign = '-' if seconds < 0 else '+'
    hours, rest = divmod(abs(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return '%s%02d%02d%s' % (sign, hours, minutes, '%02d' % secs if secs else '')


def vtimezone(tzid, start, end):
    """A VTIMEZONE for `tzid` that is exact between the dates `start` and `end`.

    The offset in force at `start` is the base observance; any UTC offset
    change (daylight saving) before `end` adds an observance at that instant,
    so zones without DST produce a single STANDARD block.
    """
    tz = ZoneInfo(tzid)

    def at(ts):
        return datetime.datetime.fromtimestamp(ts, tz)

    begin = int(datetime.datetime.combine(start, datetime.time(), tz).timestamp())
    stop = int(datetime.datetime.combine(end + datetime.timedelta(days=2), datetime.time(), tz).timestamp())
    first = at(begin)
    observances = [('19700101T000000', first.utcoffset(), first)]
    previous = first.utcoffset()
    cursor = begin
    while cursor < stop:
        nxt = min(cursor + 86400, stop)
        if at(nxt).utcoffset() != previous:
            lo, hi = cursor, nxt          # offset(lo) == previous != offset(hi)
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if at(mid).utcoffset() == previous:
                    lo = mid
                else:
                    hi = mid
            after = at(hi)
            # DTSTART of an observance is the local time just before the change.
            local_before = datetime.datetime.fromtimestamp(hi, UTC).replace(tzinfo=None) + previous
            observances.append((_local(local_before), previous, after))
            previous = after.utcoffset()
        cursor = nxt

    lines = ['BEGIN:VTIMEZONE', 'TZID:%s' % tzid, 'X-LIC-LOCATION:%s' % tzid]
    for dtstart, offset_from, moment in observances:
        kind = 'DAYLIGHT' if moment.dst() else 'STANDARD'
        lines += ['BEGIN:%s' % kind,
                  'DTSTART:%s' % dtstart,
                  'TZOFFSETFROM:%s' % _offset(offset_from),
                  'TZOFFSETTO:%s' % _offset(moment.utcoffset())]
        name = moment.tzname()
        if name:
            lines.append('TZNAME:%s' % escape_text(name))
        lines.append('END:%s' % kind)
    lines.append('END:VTIMEZONE')
    return lines


def build_ics(user, today=None, now=None):
    """The complete .ics document (str with CRLF line endings) for a user."""
    tzid = settings.TIME_ZONE
    tz = ZoneInfo(tzid)
    today = today or timezone.localdate()
    now = now or timezone.now()
    last_day = semester_end(today)
    # The last occurrence may start any time on the semester's last day; UNTIL
    # must be in UTC because DTSTART carries a TZID (RFC 5545 3.3.10).
    until = _utc(datetime.datetime.combine(last_day, datetime.time(23, 59, 59), tz))
    stamp = _utc(now)
    name = user.full_name or user.email

    lines = ['BEGIN:VCALENDAR',
             'VERSION:2.0',
             'PRODID:%s' % PRODID,
             'CALSCALE:GREGORIAN',
             'METHOD:PUBLISH',
             'X-WR-CALNAME:%s' % escape_text('SAS · %s' % name),
             'X-WR-CALDESC:%s' % escape_text('Weekly timetable from SAS until %s'
                                             % last_day.strftime('%d %b %Y')),
             'X-WR-TIMEZONE:%s' % tzid,
             'REFRESH-INTERVAL;VALUE=DURATION:PT6H',
             'X-PUBLISHED-TTL:PT6H']
    events = [e for e in events_for(user, today) if e['start'].date() <= last_day]
    first_day = min((e['start'].date() for e in events), default=today)
    lines += vtimezone(tzid, first_day, last_day)

    for event in events:
        lines += ['BEGIN:VEVENT',
                  'UID:%s' % event['uid'],
                  'DTSTAMP:%s' % stamp,
                  'DTSTART;TZID=%s:%s' % (tzid, _local(event['start']))]
        if event['end'] > event['start']:
            lines.append('DTEND;TZID=%s:%s' % (tzid, _local(event['end'])))
        lines += ['RRULE:FREQ=WEEKLY;UNTIL=%s' % until,
                  'SUMMARY:%s' % escape_text(event['summary']),
                  'LOCATION:%s' % escape_text(event['location']),
                  'DESCRIPTION:%s' % escape_text(event['description']),
                  'CATEGORIES:%s' % escape_text(event['slot'].lec_type),
                  'TRANSP:OPAQUE',
                  'END:VEVENT']
    lines.append('END:VCALENDAR')
    return '\r\n'.join(fold(line) for line in lines) + '\r\n'
