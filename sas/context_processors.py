from django.conf import settings


def navigation(request):
    """Expose which sidebar section is active and the attendance threshold."""
    nav = ''
    match = getattr(request, 'resolver_match', None)
    if match is not None:
        nav = match.func.__module__.split('.')[0]
        if match.url_name in ('profile', 'password-change'):
            nav = 'profile'
    return {
        'nav': nav,
        'attendance_threshold': settings.ATTENDANCE_THRESHOLD,
    }
