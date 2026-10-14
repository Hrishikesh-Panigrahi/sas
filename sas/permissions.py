"""Role checks shared by every app.

Roles, from most to least privileged:
- superuser: everything, across departments
- HOD (`is_hod`): manages courses, teachers, classes and students in their department
- class teacher (`is_classteacher`): manages classes and students in their department
- teacher (`is_staff`): takes attendance and views the timetable
- student (not staff): sees their own attendance
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def _role_required(check):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def inner(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return inner
    return decorator


staff_required = _role_required(lambda u: u.is_staff or u.is_superuser)
hod_required = _role_required(lambda u: u.can_manage_department)
manager_required = _role_required(lambda u: u.can_manage_students)


def in_department(queryset, user, field='department'):
    """Limit a queryset to the user's department (superusers without one see all)."""
    if user.is_superuser and not user.department:
        return queryset
    return queryset.filter(**{field: user.department})


def linked_records(*pairs):
    """Describe what a delete will cascade to, e.g. ['3 lectures'], skipping zeros."""
    return ['%d %s%s' % (n, label, '' if n == 1 else 's') for n, label in pairs if n]
