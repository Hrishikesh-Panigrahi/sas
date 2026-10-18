from django.conf import settings


def navigation(request):
    """Expose which sidebar section is active and the attendance threshold."""
    nav = ''
    match = getattr(request, 'resolver_match', None)
    if match is not None:
        nav = match.func.__module__.split('.')[0]
        if match.url_name in ('profile', 'password-change'):
            nav = 'profile'
        elif match.url_name in ('checkin-code', 'checkin-scan'):
            nav = 'checkin'
        elif match.url_name in ('defaulters',):
            nav = 'defaulters'
        elif match.url_name == 'ask':
            nav = 'ask'
        elif match.url_name == 'cover':
            nav = 'cover'
        elif match.url_name == 'calendar':
            nav = 'calendar'
    pending_leave = 0
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.can_manage_students:
        from leave.views import reviewable
        pending_leave = reviewable(user).filter(status='pending').count()
    return {
        'nav': nav,
        'attendance_threshold': settings.ATTENDANCE_THRESHOLD,
        'pending_leave': pending_leave,
    }
