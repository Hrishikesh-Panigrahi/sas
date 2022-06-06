from django.forms import ModelForm
from course.models import Course


class CourseForm(ModelForm):
    class Meta:
        model = Course
        # fields = ['name', 'sem', 'dept', 'is_elective',
        #           'dept_level', 'institue_level']
        fields = '__all__'
