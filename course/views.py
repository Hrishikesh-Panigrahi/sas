from django.http import HttpResponse, HttpResponseRedirect
from django.views import View
from django.shortcuts import redirect, render
from course.forms import CourseForm
from course.models import Course
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required



# class Index(View):
#     def get(self, request):
#         # return HttpResponse("hello world")
#         return render(request, 'course/create.html')

# def index(request):
#     c = Course.objects.all()
#     return render(request, 'course/index.html', {'courses': c})
@login_required(login_url='/')
def index(request):
    courses = Course.objects.all()
    context = {
        'title': 'Courses',
        'page': 'table',
        'courses': courses,
        'range': range(60)
    }
    return render(request, 'course/courses.html', context)

@staff_member_required(login_url='/')
def create(request):
    form = CourseForm()
    context = {
        'title': 'Courses',
        'type': 'Create',
        'form': form
    }

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            print("success")
            form.save()
        return redirect(index)
    return render(request, 'course/CourseForm.html', context)

@staff_member_required(login_url='/')
def update(request, id):
    course = Course.objects.get(pk=id)
    form = CourseForm(instance=course)
    context = {
        'title': 'Courses',
        'form': form,
        'type': 'Update',
        'id': course.id
    }

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            print("success")
            form.save()
            return redirect(update, id)
    return render(request, 'course/CourseForm.html', context)

@staff_member_required(login_url='/')
def delete(request, id):
    course = Course.objects.get(pk=id)
    context = {
        'title': 'Courses',
        'id': course.id
    }
    if request.method == 'POST':
        course.delete()
        return redirect(index)
    return render(request, 'course/delete.html', context)
