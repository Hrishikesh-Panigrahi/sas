import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from attendance.models import Assign_cls
from cls.models import Class
from sas import ai
from sas.permissions import in_department, staff_required
from . import assistant, generator as gen
from .forms import SlotForm
from .models import TimeTable

DAYS = [day for day, _ in TimeTable.day_choices]


def _week(slots, teachers):
    """Group slots by weekday, attaching the teacher of each class + course."""
    week = {day: [] for day in DAYS}
    for slot in slots:
        slot.teachers = teachers.get((slot.cls_id, slot.course_id), [])
        week.setdefault(slot.day, []).append(slot)
    days = DAYS + [d for d in ('Saturday',) if week.get(d)]
    return [(day, week[day]) for day in days]


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


def _managed_class(request, cls_id):
    if not request.user.can_manage_students:
        raise PermissionDenied
    return get_object_or_404(in_department(Class.objects.all(), request.user), pk=cls_id)


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return {}


@staff_required
def generator(request, cls_id):
    cls = _managed_class(request, cls_id)
    context = {
        'title': 'Timetable generator · %s' % cls.class_name,
        'cls': cls,
        'config': gen.default_config(cls),
        'existing': cls.timetable_set.count(),
        'claude': ai.enabled(),
    }
    return render(request, 'timetable/generator.html', context)


@staff_required
@require_POST
def generator_run(request, cls_id):
    cls = _managed_class(request, cls_id)
    body = _json_body(request)
    try:
        config = gen.clean_config(cls, body.get('config'))
    except gen.ConfigError as e:
        return JsonResponse({'error': str(e)}, status=400)
    seed = body.get('seed') if isinstance(body.get('seed'), int) else 0
    result = gen.generate(cls, config, seed=seed)
    # Keep the exact result so "Apply" saves what the user saw.
    request.session['timetable_draft_%d' % cls.id] = {'slots': result['slots']}
    return JsonResponse(result)


@staff_required
@require_POST
def generator_assist(request, cls_id):
    cls = _managed_class(request, cls_id)
    text = str(_json_body(request).get('text', ''))[:2000]
    return JsonResponse(assistant.parse(text, gen.context(cls)))


@staff_required
@require_POST
def generator_apply(request, cls_id):
    cls = _managed_class(request, cls_id)
    draft = request.session.get('timetable_draft_%d' % cls.id)
    if not draft or not draft.get('slots'):
        return JsonResponse({'error': 'Generate a timetable first.'}, status=400)
    clashes = gen.conflicts(cls, draft['slots'])
    if clashes:
        return JsonResponse({'error': "Another class's timetable changed since you generated this one "
                                      "(%s). Generate again." % ', '.join(clashes[:3])}, status=409)
    count = gen.apply(cls, draft['slots'])
    del request.session['timetable_draft_%d' % cls.id]
    messages.success(request, 'Saved a new timetable for %s with %d slots.' % (cls.class_name, count))
    return JsonResponse({'redirect': reverse('timetable-class', args=[cls.id])})
