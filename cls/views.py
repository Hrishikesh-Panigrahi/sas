from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from cls.filters import StudentFilter, CourseFilter
from course.models import Course
from users.models import TeacherProfile, User
from .forms import ClassCreateForm, ClassUpdateForm
from .models import Class
from student.models import student
from attendance.models import Assign_cls, Attendance, AttendanceClass

from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required(login_url='/')
def index(request):
    uDept = request.user.department
    return HttpResponse("helo")


@staff_member_required(login_url='/')
def create(request):
    uDept = request.user.department

    # getting teacher and students
    t = TeacherProfile.objects.filter(
        user__department=uDept, user__is_classteacher=True, class__class_teacher=None)
    s = student.objects.filter(user__department=uDept, cls=None)

    # getting course of the department
    co = Course.objects.filter(dept=uDept)
    filter = StudentFilter(request.GET, queryset=s)
    cfilter = CourseFilter(request.GET, queryset=co)
    form = ClassCreateForm(None, students=s, course=co, teachers=t)
    context = {
        'form': form,
        'filter1': filter,
        'cfilter': cfilter

    }
    if request.method == 'POST':
        form = ClassCreateForm(request.POST, students=s, course=co, teachers=t)

        if form.is_valid():

            body = request.POST.dict()
            teacher = t.get(pk=request.POST['teacher'])
            students = dict(request.POST)['students']

            course = None
            if 'course' in dict(request.POST):
                course = dict(request.POST)['course']
                print(course)
            c = Class(class_name=body['name'],
                      department=uDept, class_teacher=teacher)
            c.save()

            for obj in students:
                s = student.objects.get(pk=obj)
                s.cls = c
                if course:
                    s.course.add(*course)
                s.save()

    return render(request, 'cls/form.html', context)


@staff_member_required(login_url='/')
def update(request, id):
    uDept = request.user.department
    c = Class.objects.get(pk=id)
    in_class = student.objects.filter(cls=c, user__department=uDept)
    out_class = student.objects.filter(cls=None, user__department=uDept)
    inStudentFilter = StudentFilter(request.GET, queryset=in_class)
    in_class = inStudentFilter.qs

    outStudentFilter = StudentFilter(request.GET, queryset=out_class)
    out_class = outStudentFilter.qs

    form = ClassUpdateForm(request.POST or None, instance=c,
                           in_class=in_class, out_class=out_class)

    if request.method == 'POST' and form.is_valid():
        form.save()
        in_cstudents = dict(request.POST)['students in class']
        out_cstudents = dict(request.POST)['students not in class']
        for obj in out_cstudents:
            s = student.objects.get(pk=obj)
            # AssignCourse.course_assign(s, c)

            s.cls = c
            s.save()
        for obj in in_cstudents:
            s = student.objects.get(pk=obj)
            s.cls = None
            s.save()

    context = {
        "form": form,
        "filter1": inStudentFilter
    }
    return render(request, 'cls/form.html', context)


def clsCreation(request):
    uDept = request.user.department
    t = TeacherProfile.objects.filter(user__department=uDept)
    course = Course.objects.filter(dept=uDept)
    s = student.objects.filter(user__department=uDept, cls=None)

    context = {
        'course': course,
        'stu': s,
        't':t
    }

    if request.method == 'POST':

        clsname = request.POST['ClassName']
        cls = Class(class_name=clsname, department=uDept)
        cls.save()

        if 'course' in dict(request.POST):
            courses = dict(request.POST)['course']
            if 'teacher' in dict(request.POST):
                teacher =  dict(request.POST)['teacher']
                              
                for course,t in zip(courses,teacher):
                    co = Course.objects.get(name=course)
                    print(t)
                    te = TeacherProfile.objects.get(user__first_name=t)
                    Assign_cls.objects.get_or_create(cls=cls, course=co, teacher = te)
                    
        if 'students' in dict(request.POST):
            students = dict(request.POST)['students']

            for obj in students:
                s = student.objects.get(user__first_name=obj)
                s.cls = cls

                if courses:

                    for course in courses:
                        co = Course.objects.get(name=course)
                        s.course.add(co)

                s.save()
        # return redirect('courseteach', name=clsname)
        return redirect("/")

    return render(request, 'cls/class-section1.html', context)


'''def assigncourse(request, name):
    assclass = Assign_cls.objects.filter(cls__class_name=name)
    uDept = request.user.department
    t = TeacherProfile.objects.filter(user__department=uDept)
    context = {'assclass': assclass,
               't': t}

    for i in assclass:
        y = 1
        temp = i.cls.class_name
        if(y > 1):
            continue
        context.update({'temp': temp})
        y += 1

    if request.method == 'POST':
# assclass -> array , course -> condition, teacher -> value

        if 'course' in dict(request.POST):
            course = dict(request.POST)['course']
            if 'teacher' in dict(request.POST):
                teacher = dict(request.POST)['teacher']

            # queryset ka teacher

                for i in assclass:
                    if course in i.course__name:
                        k=TeacherProfile.objects.filter(user__first_name=teacher)
                        print(k)
                        i.teacher = k
                        i.save()
                    

                    # for teacher in teacher:
                    #     teach = TeacherProfile.objects.get(user__first_name=teacher)
                    #     i.teacher = teach
                    #     i.save()

    return render(request, 'cls/course-teacher-section.html', context)'''
