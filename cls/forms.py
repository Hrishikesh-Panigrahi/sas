from django import forms
from django.db.models import Q

from attendance.models import Assign_cls
from cls.models import Class
from sas.forms import BootstrapFormMixin
from student.models import student


class ClassForm(BootstrapFormMixin, forms.ModelForm):
    """Create or edit a class: its name, class teacher, courses and students.

    Course assignments are submitted as `course_<id>` checkboxes with a
    matching `teacher_<id>` select, one row per department course.
    """
    students = forms.ModelMultipleChoiceField(
        queryset=student.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Class
        fields = ['class_name', 'class_teacher']
        labels = {'class_name': 'Class name', 'class_teacher': 'Class teacher'}
        widgets = {'class_name': forms.TextInput(attrs={'placeholder': 'e.g. TE COMPS A'})}

    def __init__(self, *args, courses, teachers, students, **kwargs):
        super().__init__(*args, **kwargs)
        cls = self.instance if self.instance.pk else None
        # Offer teachers/students who are free, plus whoever is already in this class.
        free_teacher = Q(**{'class__isnull': True})
        free_student = Q(cls__isnull=True)
        if cls:
            free_teacher |= Q(**{'class': cls})
            free_student |= Q(cls=cls)
        self.fields['class_teacher'].queryset = (
            teachers.filter(user__is_classteacher=True).filter(free_teacher))
        self.fields['class_teacher'].empty_label = 'No class teacher yet'
        self.fields['class_teacher'].help_text = (
            'Lists teachers marked "can be a class teacher" who do not already lead a class.')
        self.fields['students'].queryset = students.filter(free_student)
        if cls and not self.is_bound:
            self.fields['students'].initial = list(cls.student_set.values_list('pk', flat=True))

        self.courses = courses
        self.teachers = teachers
        self.assignment_errors = {}
        self.existing = {}
        if cls:
            for a in cls.assign_cls_set.select_related('teacher').order_by('id'):
                self.existing.setdefault(a.course_id, []).append(a)

    def course_rows(self):
        """Rows for the course/teacher table, reflecting submitted data if any."""
        rows = []
        for course in self.courses:
            current = self.existing.get(course.id, [])
            if self.is_bound:
                checked = ('course_%d' % course.id) in self.data
                teacher_id = self.data.get('teacher_%d' % course.id, '')
            else:
                checked = bool(current)
                teacher_id = str(current[0].teacher_id) if current else ''
            rows.append({'course': course, 'checked': checked, 'teacher_id': teacher_id,
                         'error': self.assignment_errors.get(course.id)})
        return rows

    def selected_student_ids(self):
        return {str(pk) for pk in (self['students'].value() or [])}

    def clean(self):
        cleaned = super().clean()
        self.assignment_errors = {}
        self.assignments = {}
        teachers = {str(t.pk): t for t in self.teachers}
        for course in self.courses:
            if ('course_%d' % course.id) not in self.data:
                continue
            teacher = teachers.get(self.data.get('teacher_%d' % course.id, ''))
            if teacher is None:
                self.assignment_errors[course.id] = 'Choose who teaches this course.'
            else:
                self.assignments[course.id] = teacher
        if self.assignment_errors:
            raise forms.ValidationError('Pick a teacher for every course you selected.')
        return cleaned

    def save(self, department=None):
        cls = super().save(commit=False)
        if department and not cls.department:
            cls.department = department
        cls.save()

        selected = set(s.pk for s in self.cleaned_data['students'])
        cls.student_set.exclude(pk__in=selected).update(cls=None)
        student.objects.filter(pk__in=selected).update(cls=cls)

        kept = []
        for course in self.courses:
            current = self.existing.get(course.id, [])
            teacher = self.assignments.get(course.id)
            if teacher is not None:
                if not current:
                    Assign_cls.objects.create(cls=cls, course=course, teacher=teacher)
                elif all(a.teacher_id != teacher.pk for a in current):
                    # Hand the course (and its attendance history) to the new teacher.
                    current[0].teacher = teacher
                    current[0].save()
            else:
                for a in current:
                    if a.attendanceclass_set.exists():
                        kept.append(course)
                    else:
                        a.delete()

        course_ids = list(cls.assign_cls_set.values_list('course', flat=True))
        for stu in cls.student_set.all():
            stu.course.add(*course_ids)
        # Courses that could not be removed because lectures were recorded.
        self.kept_courses = sorted(set(kept), key=lambda c: c.name)
        return cls
