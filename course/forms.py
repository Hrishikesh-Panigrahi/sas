from django import forms
from django.forms import CheckboxSelectMultiple, ModelForm, ModelMultipleChoiceField
from course.models import Course
from users.models import TeacherProfile


class CourseForm(ModelForm):
    class Meta:
        model = Course
        fields = ['scheme', 'code', 'name', 'dept', 'sem', 'is_elective',
                  'dept_level', 'institue_level']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'scheme': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'dept': forms.HiddenInput(attrs={'class': 'form-control'}),
            'sem': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        d = kwargs.pop('dept', None)
        super(CourseForm, self).__init__(*args, **kwargs)
        self.fields['dept'].initial = d

    # taught_by = ModelMultipleChoiceField(
    #     queryset=TeacherProfile.objects.all(), widget=CheckboxSelectMultiple)

    # add dept as params in CoureForm Object
    # dept should be as per dept_choices
    # def __init__(self, dept, *args, **kwargs):
    #     super(CourseForm, self).__init__(*args, **kwargs)
    #     self.fields['dept'].initial = dept
    #     self.fields['dept'].disabled = True
    #     self.fields['taught_by'].queryset = TeacherProfile.objects.filter(
    #         department=dept)

    # For testing ignore
    # def __init__(self, *args, **kwargs):
    #     dept = 'Computer Engineering'
    #     super(CourseForm, self).__init__(*args, **kwargs)
    #     self.fields['dept'].initial = dept
    #     self.fields['dept'].disabled = True
    #     self.fields['taught_by'].queryset = TeacherProfile.objects.filter(
    #         department=dept)
