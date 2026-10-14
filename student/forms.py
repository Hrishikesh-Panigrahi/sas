from django import forms

from cls.models import Class
from users.forms import UserAccountForm


class StudentForm(UserAccountForm):
    roll_no = forms.IntegerField(label='Roll number', required=False, min_value=1)
    cls = forms.ModelChoiceField(label='Class', queryset=Class.objects.none(), required=False,
                                 empty_label='Not in a class yet')
    batch = forms.ChoiceField(label='Lab batch', required=False,
                              choices=[('', 'None'), ('A', 'A'), ('B', 'B'), ('C', 'C')])

    class Meta(UserAccountForm.Meta):
        pass

    field_order = ['first_name', 'last_name', 'email', 'roll_no', 'cls', 'batch', 'password1', 'password2']

    def __init__(self, *args, profile=None, classes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.fields['cls'].queryset = classes if classes is not None else Class.objects.none()
        self.fields['cls'].widget.attrs['class'] = 'custom-select'
        self.fields['roll_no'].widget.attrs['class'] = 'form-control'
        self.fields['batch'].widget.attrs['class'] = 'custom-select'
        if profile is not None:
            self.fields['roll_no'].initial = profile.roll_no
            self.fields['cls'].initial = profile.cls_id
            self.fields['batch'].initial = profile.batch
        self.order_fields(self.field_order + ['department'])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.save()
        # Saving the user creates the student profile (see users/signals.py).
        profile = user.student
        profile.roll_no = self.cleaned_data.get('roll_no')
        profile.cls = self.cleaned_data.get('cls')
        profile.batch = self.cleaned_data.get('batch') or ''
        profile.save()
        if profile.cls:
            courses = profile.cls.assign_cls_set.values_list('course', flat=True)
            profile.course.add(*courses)
        return user
