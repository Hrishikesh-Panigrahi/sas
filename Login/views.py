from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme


def loginUser(request):
    if request.user.is_authenticated:
        return redirect('index')

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    email = ''

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            # Only follow `next` when it points back into this site.
            if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()},
                    require_https=request.is_secure()):
                return redirect(next_url)
            return redirect('index')
        messages.error(request, 'That email and password combination is not correct.')

    return render(request, 'Login/login.html', {'next': next_url, 'email': email})


def logoutUser(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'You have been signed out.')
    return redirect('Login')
