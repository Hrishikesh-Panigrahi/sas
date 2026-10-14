from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from attendance.models import Assign_cls
from cls.models import Class
from sas.permissions import in_department, staff_required
from .forms import SlotForm
from .models import TimeTable

DAYS = [day for day, _ in TimeTable.day_choices]


def _week(slots, teachers):
    """Group slots by weekday, attaching the teacher of each class + course."""
    week = {day: [] for day in DAYS}
    for slot in slots:
        slot.teachers = teachers.get((slot.cls_id, slot.course_id), [])
        week.setdefault(slot.day, []).append(slot)
    return [(day, week[day]) for day in DAYS]


def _teachers_by_pair(assignments):
    teachers = {}
    for a in assignments.select_related('teacher__user'):
        teachers.setdefault((a.cls_id, a.course_id), []).append(a.teacher.user.full_name)
    return teachers


@staff_required
def index(request):
    user = request.user
    mine = Assign_cls.objects.filter(teacher__user=user)
    pairs = {(a.cls_id, a.course_id) for a in mine}
    my_slots = [s for s in TimeTable.objects.filter(cls__in={c for c, _ in pairs})
                .select_related('cls', 'course').order_by('start_time')
                if (s.cls_id, s.course_id) in pairs]
    context = {
        'title': 'Timetable',
        'week': _week(my_slots, {}) if my_slots else None,
        'today': timezone.localdate().strftime('%A'),
        'classes': in_department(Class.objects.all(), user).order_by('class_name'),
    }
    return render(request, 'timetable/index.html', context)


@staff_required
def class_timetable(request, cls_id):
    cls = get_object_or_404(in_department(Class.objects.all(), request.user), pk=cls_id)
    can_edit = request.user.can_manage_students
    form = SlotForm(request.POST or None, cls=cls)
    if request.method == 'POST':
        if not can_edit:
            raise PermissionDenied
        if form.is_valid():
            slot = form.save(commit=False)
            slot.cls = cls
            slot.save()
            messages.success(request, 'Added %s on %s, %s.' % (slot.course, slot.day, slot.period))
            return redirect('timetable-class', cls_id=cls.id)

    slots = cls.timetable_set.select_related('cls', 'course').order_by('start_time')
    context = {
        'title': 'Timetable · %s' % cls.class_name,
        'cls': cls,
        'week': _week(slots, _teachers_by_pair(cls.assign_cls_set.all())),
        'today': timezone.localdate().strftime('%A'),
        'can_edit': can_edit,
        'form': form,
        'has_courses': cls.assign_cls_set.exists(),
    }
    return render(request, 'timetable/class.html', context)


@staff_required
@require_POST
def delete_slot(request, id):
    slot = get_object_or_404(TimeTable.objects.select_related('cls', 'course'), pk=id)
    in_scope = in_department(Class.objects.filter(pk=slot.cls_id), request.user).exists()
    if not (request.user.can_manage_students and in_scope):
        raise PermissionDenied
    slot.delete()
    messages.success(request, 'Removed %s on %s, %s.' % (slot.course, slot.day, slot.period))
    return redirect('timetable-class', cls_id=slot.cls_id)
