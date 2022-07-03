from django.http import HttpResponse
from django.shortcuts import redirect
from sas.views import index


def hod_allowed(view_func):
    def inner(request, *args, **kwargs):
        if request.user.is_authenticated:
            users=request.user
            if users.is_hod:
                print(users.is_hod)
                return view_func(request, *args, **kwargs)

            else:
                return redirect('Login')

        else:
            return redirect('Login')

    return inner