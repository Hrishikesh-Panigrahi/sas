from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from sas.permissions import in_department
from student.models import student
from .forms import LeaveForm
from .models import LeaveRequest
from .services import lectures_in_range, sync_excuses


def reviewable(user):
    """Leave requests this user may decide: their own class for a class teacher, the department for an HOD."""
    if not user.is_authenticated or not user.can_manage_students:
        return LeaveRequest.objects.none()
    qs = LeaveRequest.objects.select_related('student__user', 'student__cls')
    if user.can_manage_department:
        return in_department(qs, user, 'student__user__department')
    led = getattr(getattr(user, 'teacherprofile', None), 'class', None)
    if led is not None:
        return qs.filter(student__cls=led)
    return in_department(qs, user, 'student__user__department')


@login_required
def index(request):
    if request.user.is_student:
        return _student_page(request)
    if request.user.can_manage_students:
        return _inbox(request)
    raise PermissionDenied


def _student_page(request):
    me = get_object_or_404(student, user=request.user)
    form = LeaveForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        leave = form.save(me)
        messages.success(request, 'Your leave request for %s was sent to your class teacher.'
                         % _span(leave))
        return redirect('leave')
    requests = list(me.leave_requests.all())
    for leave in requests:
        leave.lectures = lectures_in_range(leave).count()
    context = {'title': 'Leave', 'form': form, 'requests': requests}
    return render(request, 'leave/student.html', context)


def _inbox(request):
    status = request.GET.get('status', 'pending')
    if status not in ('pending', 'approved', 'rejected'):
        status = 'pending'
    scope = reviewable(request.user)
    requests = list(scope.filter(status=status).select_related('reviewed_by'))
    for leave in requests:
        leave.lectures = lectures_in_range(leave).count()
    counts = {s: scope.filter(status=s).count() for s in ('pending', 'approved', 'rejected')}
    context = {'title': 'Leave requests', 'requests': requests, 'status': status, 'counts': counts}
    return render(request, 'leave/inbox.html', context)


def _span(leave):
    if leave.start_date == leave.end_date:
        return leave.start_date.strftime('%d %b')
    return '%s – %s' % (leave.start_date.strftime('%d %b'), leave.end_date.strftime('%d %b'))


@login_required
@require_POST
def review(request, pk):
    leave = get_object_or_404(reviewable(request.user), pk=pk)
    action = request.POST.get('action')
    if action not in ('approve', 'reject'):
        return redirect('leave')
    leave.status = 'approved' if action == 'approve' else 'rejected'
    leave.reviewed_by = request.user
    leave.reviewed_at = timezone.now()
    leave.review_note = request.POST.get('note', '').strip()[:300]
    leave.save()
    excused = sync_excuses(leave.student, leave.start_date, leave.end_date)
    name = leave.student.user.full_name
    if leave.status == 'approved':
        messages.success(request, "Approved %s's leave (%s). %s now excused."
                         % (name, _span(leave), '%d absence%s %s' % (
                             excused, '' if excused == 1 else 's', 'is' if excused == 1 else 'are')
                         if excused else 'Any absences in that period are'))
    else:
        messages.info(request, "Didn't approve %s's leave (%s)." % (name, _span(leave)))
    return redirect('/leave/?status=%s' % ('pending' if request.POST.get('from') == 'pending' else leave.status))


@login_required
@require_POST
def cancel(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk, student__user=request.user, status='pending')
    leave.status = 'cancelled'
    leave.save()
    messages.info(request, 'Cancelled your leave request for %s.' % _span(leave))
    return redirect('leave')


@login_required
def document(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    owner = leave.student.user_id == request.user.id
    if not owner and not reviewable(request.user).filter(pk=pk).exists():
        raise PermissionDenied
    if not leave.has_document:
        return redirect('leave')
    response = HttpResponse(bytes(leave.document), content_type=leave.document_type)
    response['Content-Disposition'] = 'inline; filename="%s"' % leave.document_name.replace('"', '')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
