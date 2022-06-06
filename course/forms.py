from django.forms import ModelForm
from course.models import Course
from users.models import TeacherProfile


class CourseForm(ModelForm):
    class Meta:
        model = Course
        # fields = ['name', 'sem', 'is_elective', 'taught_by',
        #           'dept_level', 'institue_level']
        fields = '__all__'

    # add dept as params in CoureForm Object
    # dept should be as per dept_choices
    # def __init__(self, dept, *args, **kwargs):
    #     super(CourseForm, self).__init__(*args, **kwargs)
    #     self.fields['dept'].initial = dept
    #     self.fields['dept'].disabled = True
    #     self.fields['taught_by'].queryset = TeacherProfile.objects.filter(
    #         department=dept)
