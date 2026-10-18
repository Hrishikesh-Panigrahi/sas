"""Calendar subscription: the secret .ics feed and the page that hands it out."""
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_safe

from sas.semester import semester_end
from . import calendar_feed


@require_safe
def feed(request, token):
    """The .ics feed. No login: the signed token in the URL is the credential."""
    pk = calendar_feed.user_pk_from_token(token)
    user = get_user_model().objects.filter(pk=pk, is_active=True).first() if pk else None
    if user is None:
        raise Http404('No such calendar.')
    response = HttpResponse(calendar_feed.build_ics(user), content_type='text/calendar; charset=utf-8')
    disposition = 'attachment' if request.GET.get('download') else 'inline'
    response['Content-Disposition'] = '%s; filename="sas-timetable.ics"' % disposition
    # Calendar apps poll on their own schedule; keep shared caches out of it.
    response['Cache-Control'] = 'private, max-age=900'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@login_required
def page(request):
    user = request.user
    token = calendar_feed.make_token(user)
    feed_url = request.build_absolute_uri(reverse('calendar-feed', args=[token]))
    webcal_url = 'webcal://' + feed_url.split('://', 1)[1]

    events = calendar_feed.events_for(user)
    days = []
    for event in events:
        day = event['slot'].day
        if not days or days[-1][0] != day:
            days.append((day, []))
        days[-1][1].append(event)

    context = {
        'title': 'Calendar sync',
        'feed_url': feed_url,
        'webcal_url': webcal_url,
        'download_url': feed_url + '?download=1',
        'google_url': 'https://calendar.google.com/calendar/r?cid=' + quote(webcal_url, safe=''),
        'days': days,
        'num_events': len(events),
        'semester_end': semester_end(),
        'today': timezone.localdate().strftime('%A'),
    }
    return render(request, 'timetable/calendar.html', context)
