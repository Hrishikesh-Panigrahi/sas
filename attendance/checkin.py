"""Live QR check-in.

The teacher projects a QR code (and a 6-digit code for anyone without a camera)
that changes every `window` seconds. Each code is an HMAC of the session secret
and the current time window, so a photo of the screen stops working within
seconds. A phone can check in only one student per session, and only students
expected at the lecture (its class, and batch for labs) can check in.
"""
import hashlib
import hmac
import secrets
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from leave.services import excuse_lecture
from sas.permissions import staff_required
from student.models import ROLL_ORDER, student
from .models import Attendance, AttendanceClass, CheckIn, CheckInSession

DEVICE_COOKIE = 'sas_device'
SESSION_HOURS = 3


# ------------------------------------------------------------------ codes

def _digest(session, window):
    return hmac.new(session.secret.encode(), str(window).encode(), hashlib.sha256).hexdigest()


def current_window(session, now=None):
    return int((now or time.time()) // session.window)


def url_token(session, window):
    return _digest(session, window)[:16]


def short_code(session, window):
    return '%06d' % (int(_digest(session, window)[16:24], 16) % 1000000)


def _valid(session, check, kind, now=None):
    """Accept the current code and the previous one (scanning takes a moment)."""
    w = current_window(session, now)
    make = url_token if kind == 'token' else short_code
    return any(hmac.compare_digest(make(session, x), check) for x in (w, w - 1))


def is_open(session):
    return session.closed_at is None and \
        session.started_at > timezone.now() - timezone.timedelta(hours=SESSION_HOURS)


# ------------------------------------------------------------------ teacher side

def _teacher_lecture(request, lecture_id):
    from .views import _get_assignment
    lecture = get_object_or_404(AttendanceClass.objects.select_related('assign__cls', 'assign__course'),
                                pk=lecture_id)
    _get_assignment(request, lecture.assign_id, mark=True, lecture=lecture)
    return lecture


@staff_required
@require_POST
def start(request, lecture_id):
    lecture = _teacher_lecture(request, lecture_id)
    session = lecture.checkin_sessions.filter(closed_at__isnull=True).order_by('-started_at').first()
    if session is None or not is_open(session):
        session = CheckInSession.objects.create(lecture=lecture, secret=secrets.token_hex(32),
                                                started_by=request.user)
    return redirect('checkin-live', lecture_id=lecture.id)


@staff_required
def live(request, lecture_id):
    lecture = _teacher_lecture(request, lecture_id)
    session = lecture.checkin_sessions.filter(closed_at__isnull=True).order_by('-started_at').first()
    if session is None or not is_open(session):
        messages.info(request, 'Start a live check-in from the attendance page.')
        return redirect('attendance', attendancecls_id=lecture.id)
    context = {
        'title': 'Live check-in',
        'lecture': lecture,
        'assign': lecture.assign,
        'session': session,
        'expected': lecture.students().count(),
        'state_url': reverse('checkin-state', args=[lecture.id]),
        'code_url': request.build_absolute_uri(reverse('checkin-code')),
    }
    return render(request, 'attendance/checkin_live.html', context)


@staff_required
def state(request, lecture_id):
    """Polled by the projector page: the current code (QR only when it changed) and who's in."""
    import segno
    lecture = _teacher_lecture(request, lecture_id)
    session = lecture.checkin_sessions.filter(closed_at__isnull=True).order_by('-started_at').first()
    if session is None or not is_open(session):
        return JsonResponse({'closed': True})
    now = time.time()
    w = current_window(session, now)
    data = {
        'window': w,
        'code': short_code(session, w),
        'seconds_left': round(session.window - (now % session.window), 1),
        'period': session.window,
    }
    if str(w) != request.GET.get('have'):
        url = request.build_absolute_uri(reverse('checkin-scan', args=[session.id, url_token(session, w)]))
        data['svg'] = segno.make(url, error='m').svg_inline(scale=1, border=2, dark='#0f172a', omitsize=True)
    checkins = session.checkins.select_related('student__user').order_by('-created_at')
    data['count'] = checkins.count()
    data['people'] = [{'name': c.student.user.full_name, 'initials': c.student.user.initials,
                       'at': timezone.localtime(c.created_at).strftime('%H:%M:%S')} for c in checkins[:60]]
    return JsonResponse(data)


@staff_required
@require_POST
def finish(request, lecture_id):
    lecture = _teacher_lecture(request, lecture_id)
    session = lecture.checkin_sessions.filter(closed_at__isnull=True).order_by('-started_at').first()
    if session is None:
        return redirect('attendance', attendancecls_id=lecture.id)
    if request.POST.get('action') == 'cancel':
        session.delete()
        messages.info(request, 'Live check-in cancelled. Nothing was saved.')
        return redirect('attendance', attendancecls_id=lecture.id)
    here = set(session.checkins.values_list('student_id', flat=True))
    students = list(lecture.students())
    with transaction.atomic():
        lecture.attendance_set.filter(student__in=students).delete()
        Attendance.objects.bulk_create(
            Attendance(course=lecture.assign.course, student=s, date=lecture.date,
                       attendanceclass=lecture, status=s.id in here) for s in students)
        lecture.status = 1
        lecture.save(update_fields=['status'])
        session.closed_at = timezone.now()
        session.save(update_fields=['closed_at'])
        excuse_lecture(lecture)
    messages.success(request, 'Saved from live check-in: %d present, %d absent. Adjust anything below '
                     'and save again if needed.' % (len(here), len(students) - len(here)))
    return redirect('attendance', attendancecls_id=lecture.id)


# ------------------------------------------------------------------ student side

def _device(request):
    value = request.COOKIES.get(DEVICE_COOKIE, '')
    return value if len(value) == 32 and value.isalnum() else secrets.token_hex(16)


def _respond(request, template, context, device):
    response = render(request, template, context)
    response.set_cookie(DEVICE_COOKIE, device, max_age=60 * 60 * 24 * 365, httponly=True,
                        samesite='Lax', secure=request.is_secure())
    return response


def _eligible(stu, lecture):
    if stu is None or stu.cls_id != lecture.assign.cls_id:
        return False
    return lecture.batch == 'All' or stu.batch == lecture.batch


def _check_in(request, session, device):
    """Record the check-in; returns (ok, message)."""
    lecture = session.lecture
    stu = student.objects.filter(user=request.user, user__is_staff=False).select_related('user').first()
    if not _eligible(stu, lecture):
        return False, "This check-in is for %s%s, and you're not on its list." % (
            lecture.assign.cls.class_name, '' if lecture.batch == 'All' else ' batch %s' % lecture.batch)
    if session.checkins.filter(student=stu).exists():
        return True, "You're already checked in."
    other = session.checkins.filter(device=device).exclude(student=stu).select_related('student__user').first()
    if other:
        return False, ('This phone was already used to check in %s. Each student has to check in on '
                       'their own phone.' % other.student.user.first_name)
    try:
        CheckIn.objects.create(session=session, student=stu, device=device)
    except IntegrityError:
        pass
    return True, "You're checked in."


@login_required
def scan(request, session_id, token):
    """Opened by scanning the QR code. Confirming is one tap, within a minute."""
    device = _device(request)
    session = get_object_or_404(CheckInSession.objects.select_related('lecture__assign__course',
                                                                       'lecture__assign__cls'), pk=session_id)
    context = {'title': 'Check in', 'lecture': session.lecture}
    if request.user.is_staff:
        context['error'] = 'Check-in is for students. You are signed in as staff.'
    elif not is_open(session):
        context['error'] = 'This check-in has finished.'
    elif request.method == 'POST':
        try:
            signing.TimestampSigner(salt='sas.checkin').unsign(request.POST.get('ticket', ''), max_age=90)
        except signing.BadSignature:
            context['error'] = 'That took a little too long. Scan the code on the screen again.'
        else:
            ok, message = _check_in(request, session, device)
            context['ok' if ok else 'error'] = message
    elif not _valid(session, token, 'token'):
        context['error'] = 'That code has expired. Scan the code on the screen again.'
    else:
        context['ticket'] = signing.TimestampSigner(salt='sas.checkin').sign('%d:%s' % (session.id, device))
    return _respond(request, 'attendance/checkin_student.html', context, device)


@login_required
def code(request):
    """For students without a camera: type the 6-digit code shown on the screen."""
    device = _device(request)
    context = {'title': 'Check in with a code'}
    if request.method == 'POST':
        entered = ''.join(ch for ch in request.POST.get('code', '') if ch.isdigit())
        stu = student.objects.filter(user=request.user, user__is_staff=False).first()
        sessions = CheckInSession.objects.filter(
            closed_at__isnull=True, started_at__gt=timezone.now() - timezone.timedelta(hours=SESSION_HOURS),
            lecture__assign__cls=stu.cls_id if stu else -1).select_related('lecture__assign__course',
                                                                             'lecture__assign__cls')
        match = next((s for s in sessions if len(entered) == 6 and _valid(s, entered, 'code')), None)
        if match is None:
            context['error'] = "That code doesn't match a check-in for your class right now. Codes change every few seconds; try the one on screen."
        else:
            context['lecture'] = match.lecture
            ok, message = _check_in(request, match, device)
            context['ok' if ok else 'error'] = message
    return _respond(request, 'attendance/checkin_code.html', context, device)
