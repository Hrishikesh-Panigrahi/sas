from django import forms
from course.models import Course
from sas.forms import BootstrapFormMixin


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'name', 'scheme', 'sem', 'dept', 'is_elective',
                  'dept_level', 'institue_level']
        labels = {
            'code': 'Course code',
            'name': 'Course name',
            'scheme': 'Scheme',
            'is_elective': 'Elective course',
            'dept_level': 'Department level',
            'institue_level': 'Institute level',
        }
        help_texts = {
            'scheme': 'Syllabus scheme, for example "R2019".',
        }
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'e.g. CSC501'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Computer Networks'}),
            'scheme': forms.TextInput(attrs={'placeholder': 'e.g. R2019'}),
        }

    def __init__(self, *args, **kwargs):
        # Department comes from the signed-in user; only a superuser without
        # a department of their own picks one.
        self.dept = kwargs.pop('dept', None)
        super().__init__(*args, **kwargs)
        if self.dept:
            del self.fields['dept']

    def save(self, commit=True):
        if self.dept:
            self.instance.dept = self.dept
        return super().save(commit)
