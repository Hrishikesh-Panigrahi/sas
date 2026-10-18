"""Defaulter list page, its PDF, and warning letters to parents."""
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify

from cls.models import Class
from sas.permissions import in_department, manager_required
from student.models import student
from .defaulters import (MAX_THRESHOLD, MIN_THRESHOLD, clean_threshold, defaulter_list_pdf,
                         defaulters, warning_letters_pdf)


def _filters(request):
    """The classes the user may pick from, the chosen class (or None) and the threshold."""
    classes = in_department(Class.objects.all(), request.user).select_related(
        'class_teacher__user').order_by('class_name')
    cls = None
    cls_id = request.GET.get('cls', '').strip()
    if cls_id:
        if not cls_id.isdigit():
            raise Http404('No such class.')
        cls = get_object_or_404(classes, pk=cls_id)
    return classes, cls, clean_threshold(request.GET.get('threshold'))


def _query(cls, threshold):
    params = {'cls': cls.id} if cls else {}
    params['threshold'] = threshold
    return urlencode(params)


def _scope_slug(report):
    if report['cls']:
        return slugify(report['cls'].class_name) or 'class'
    return slugify(report['department']) or 'all-departments'


def _pdf(content, filename):
    response = HttpResponse(content, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@manager_required
def defaulter_list(request):
    classes, cls, threshold = _filters(request)
    report = defaulters(request.user, cls=cls, threshold=threshold)
    context = {
        'title': 'Defaulter list',
        'report': report,
        'classes': classes,
        'query': _query(cls, threshold),
        'min_threshold': MIN_THRESHOLD,
        'max_threshold': MAX_THRESHOLD,
    }
    return render(request, 'attendance/defaulters.html', context)


@manager_required
def defaulter_list_download(request):
    _, cls, threshold = _filters(request)
    report = defaulters(request.user, cls=cls, threshold=threshold)
    filename = 'defaulters-%s-%s.pdf' % (_scope_slug(report), report['date'].isoformat())
    return _pdf(defaulter_list_pdf(report), filename)


@manager_required
def warning_letters(request):
    _, cls, threshold = _filters(request)
    report = defaulters(request.user, cls=cls, threshold=threshold)
    filename = 'warning-letters-%s-%s.pdf' % (_scope_slug(report), report['date'].isoformat())
    return _pdf(warning_letters_pdf(report), filename)


@manager_required
def warning_letter(request, student_id):
    students = in_department(student.objects.select_related('user', 'cls'),
                             request.user, 'user__department')
    stu = get_object_or_404(students, pk=student_id)
    threshold = clean_threshold(request.GET.get('threshold'))
    entry, report = None, None
    if stu.cls_id:
        cls = get_object_or_404(
            in_department(Class.objects.select_related('class_teacher__user'), request.user),
            pk=stu.cls_id)
        report = defaulters(request.user, cls=cls, threshold=threshold)
        entry = next((e for e in report['students'] if e['student'].id == stu.id), None)
    if entry is None:
        messages.info(request, '%s is not below %d%% in any course, so there is no letter to print.'
                      % (stu.user.full_name or stu.user.email, threshold))
        return redirect('%s?%s' % (reverse('defaulters'),
                                   _query(stu.cls if stu.cls_id else None, threshold)))
    filename = 'warning-letter-%s-%s.pdf' % (
        slugify('%s %s' % (stu.cls.class_name, stu.roll_no if stu.roll_no is not None
                           else stu.user.full_name or stu.id)) or 'student',
        report['date'].isoformat())
    return _pdf(warning_letters_pdf(report, [entry]), filename)
