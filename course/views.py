from django.http import HttpResponse
from django.views import View
from django.shortcuts import render

# Create your views here.


class Index(View):
    def get(self, request):
        return HttpResponse("hello world")
