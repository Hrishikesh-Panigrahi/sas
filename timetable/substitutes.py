"""Cover for absent teachers.

`suggest()` lists a teacher's timetabled lectures on a date and, for each, the
colleagues who are free then, best first. `assign()` records the cover; the
substitute can then take attendance for that lecture (see `is_substitute`).
"""
import datetime
from collections import defaultdict

from attendance.models import Assign_cls
from sas.permissions import in_department
from users.models import TeacherProfile
from .models import Substitution, TimeTable


def is_substitute(user, assign, date):
    """True when `user` is covering one of `assign`'s timetabled lectures on `date`."""
    return Substitution.objects.filter(
        date=date, slot__cls=assign.cls_id, slot__course=assign.course_id,
        substitute__user=user).exists()


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def teaching_on(day_name, teacher_ids=None):
    """{teacher_id: [(slot, cls_id, course_id)]} for timetabled lectures on a weekday."""
    pairs = defaultdict(set)
    qs = Assign_cls.objects.all()
    if teacher_ids is not None:
        qs = qs.filter(teacher_id__in=teacher_ids)
    for cls_id, course_id, teacher_id in qs.values_list('cls_id', 'course_id', 'teacher_id'):
        pairs[(cls_id, course_id)].add(teacher_id)
    out = defaultdict(list)
    for slot in TimeTable.objects.filter(day=day_name).select_related('cls', 'course'):
        for t in pairs.get((slot.cls_id, slot.course_id), ()):
            out[t].append(slot)
    return out


def suggest(user, absent_teacher, date):
    """The absent teacher's lectures on `date`, each with ranked free colleagues."""
    day = date.strftime('%A')
    colleagues = list(in_department(TeacherProfile.objects.filter(user__is_staff=True), user,
                                    'user__department').exclude(pk=absent_teacher.pk)
                      .select_related('user'))
    busy = teaching_on(day)
    covering = defaultdict(list)          # substitutes already booked that day
    absent_today = set()
    for sub in Substitution.objects.filter(date=date).select_related('slot'):
        covering[sub.substitute_id].append(sub.slot)
        absent_today.add(sub.absent_teacher_id)
    courses_taught = defaultdict(set)
    classes_taught = defaultdict(set)
    for t, cls_id, course_id in Assign_cls.objects.values_list('teacher_id', 'cls_id', 'course_id'):
        courses_taught[t].add(course_id)
        classes_taught[t].add(cls_id)
    existing = {s.slot_id: s for s in Substitution.objects.filter(date=date, absent_teacher=absent_teacher)
                .select_related('substitute__user')}

    lectures = []
    for slot in sorted(busy.get(absent_teacher.pk, []), key=lambda s: s.start_time):
        options = []
        for c in colleagues:
            if c.pk in absent_today:
                continue
            clash = [s for s in busy.get(c.pk, []) + covering.get(c.pk, [])
                     if s.pk != slot.pk and _overlaps(s.start_time, s.end_time, slot.start_time, slot.end_time)]
            if clash:
                continue
            load = len(busy.get(c.pk, [])) + len(covering.get(c.pk, []))
            reasons, score = [], 0
            if slot.course_id in courses_taught[c.pk]:
                reasons.append('teaches %s' % (slot.course.code if slot.course else 'this course'))
                score += 10
            if slot.cls_id in classes_taught[c.pk]:
                reasons.append('knows %s' % slot.cls.class_name)
                score += 5
            adjacent = any(s.end_time == slot.start_time or s.start_time == slot.end_time
                           for s in busy.get(c.pk, []))
            if adjacent:
                reasons.append('already on campus then')
                score += 2
            reasons.append('%d lecture%s that day' % (load, '' if load == 1 else 's'))
            score -= load
            options.append({'teacher': c, 'score': score, 'reasons': reasons, 'load': load})
        options.sort(key=lambda o: (-o['score'], o['load'], o['teacher'].user.full_name))
        lectures.append({'slot': slot, 'options': options[:6], 'assigned': existing.get(slot.pk)})
    return lectures


def assign(slot, date, absent_teacher, substitute, by):
    sub, _ = Substitution.objects.update_or_create(
        slot=slot, date=date, absent_teacher=absent_teacher,
        defaults={'substitute': substitute, 'created_by': by})
    return sub


def todays_cover(user, date):
    """Timetable slots `user` is covering on `date`, with the assignment to mark attendance against."""
    out = []
    for sub in Substitution.objects.filter(substitute__user=user, date=date) \
            .select_related('slot__cls', 'slot__course', 'absent_teacher__user'):
        a = Assign_cls.objects.filter(cls=sub.slot.cls_id, course=sub.slot.course_id,
                                      teacher=sub.absent_teacher).first() \
            or Assign_cls.objects.filter(cls=sub.slot.cls_id, course=sub.slot.course_id).first()
        if a:
            out.append({'slot': sub.slot, 'assign': a, 'sub': sub})
    return out
