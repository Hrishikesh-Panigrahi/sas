from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from attendance.models import Assign_cls
from sas import ai
from sas.permissions import in_department
from student.models import student
from .analyst import analyze
from .analytics import department_facts, student_facts, teacher_facts


def _views_for(user):
    """The insight views a user can switch between, first one is the default."""
    if user.is_student:
        return [('student', 'My attendance')]
    views = []
    if user.can_manage_students:
        views.append(('department', 'Department'))
    if not views or Assign_cls.objects.filter(teacher__user=user).exists():
        views.append(('teaching', 'My teaching'))
    return views


def _facts(request, view, student_id=None):
    """Return (kind, facts, subject_id) for a view the user is allowed to see."""
    user = request.user
    if student_id:
        if user.is_student:
            raise PermissionDenied
        stu = get_object_or_404(in_department(student.objects.filter(user__is_staff=False),
                                               user, 'user__department')
                                .select_related('user', 'cls'), pk=student_id)
        return 'staff_student', student_facts(stu), stu.id
    allowed = dict(_views_for(user))
    if view not in allowed:
        raise PermissionDenied
    if view == 'student':
        stu = student.objects.filter(user=user).select_related('user', 'cls').first()
        if stu is None:
            return 'student', None, None
        return 'student', student_facts(stu), None
    if view == 'department':
        return 'department', department_facts(user), None
    return 'teacher', teacher_facts(user), None


@login_required
def index(request):
    views = _views_for(request.user)
    view = request.GET.get('view') or views[0][0]
    if view not in dict(views):
        view = views[0][0]
    kind, facts, _ = _facts(request, view)
    context = {
        'title': 'Insights',
        'views': views,
        'view': view,
        'kind': kind,
        'facts': facts,
        'claude': ai.enabled(),
        # The built-in analyst is instant, so render it inline; Claude is fetched
        # after the page loads so the charts don't wait on it.
        'analysis': analyze(kind, facts, request.user) if facts and not ai.enabled() else None,
        'analysis_url': '%s?view=%s' % (reverse('insights-analysis'), view),
    }
    return render(request, 'insights/index.html', context)


@login_required
def analysis(request):
    student_id = request.GET.get('student')
    kind, facts, subject = _facts(request, request.GET.get('view', ''),
                                  int(student_id) if student_id and student_id.isdigit() else None)
    result = analyze(kind, facts, request.user, subject_id=subject,
                     refresh=request.GET.get('refresh') == '1') if facts else None
    template = 'insights/_teaser.html' if request.GET.get('format') == 'teaser' else 'insights/_analysis.html'
    return render(request, template, {'analysis': result, 'claude': ai.enabled(),
                                      'refresh_url': request.get_full_path()})
