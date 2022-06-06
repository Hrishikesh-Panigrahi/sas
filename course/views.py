from multiprocessing import context
from django.http import HttpResponse, HttpResponseRedirect
from django.views import View
from django.shortcuts import redirect, render
from course.forms import CourseForm
from course.models import Course

# Create your views here.


# class Index(View):
#     def get(self, request):
#         # return HttpResponse("hello world")
#         return render(request, 'course/create.html')

def index(request):
    c = Course.objects.all()
    return render(request, 'course/index.html', {'courses': c})


def create(request):
    form = CourseForm()
    context = {
        'title': 'Create',
        'form': form
    }

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            print("success")
            form.save()

    return render(request, 'course/CourseForm.html', context)


def update(request, id):
    course = Course.objects.get(pk=3)
    form = CourseForm(instance=course)
    context = {
        'title': 'Update',
        'form': form
    }

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            print("success")
            form.save()
            return redirect(update, id)
    return render(request, 'course/CourseForm.html', context)
