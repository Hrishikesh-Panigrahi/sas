from django import forms

from attendance.models import Assign_cls
from course.models import Course
from sas.forms import BootstrapFormMixin
from .models import TimeTable


class SlotForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TimeTable
        fields = ['day', 'start_time', 'end_time', 'course', 'lec_type', 'batch']
        labels = {'lec_type': 'Type', 'start_time': 'Starts', 'end_time': 'Ends'}
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, cls, **kwargs):
        super().__init__(*args, **kwargs)
        self.cls = cls
        # Only courses this class actually takes can be scheduled.
        self.fields['course'].queryset = Course.objects.filter(
            assign_cls__cls=cls).distinct().order_by('name')
        self.fields['course'].required = True
        self.fields['course'].empty_label = 'Choose a course'
        self.fields['day'].choices = [('', 'Choose a day')] + list(TimeTable.day_choices)
        self.fields['lec_type'].choices = TimeTable.lec_choices
        self.fields['batch'].choices = TimeTable.batch_choices
        self.fields['batch'].initial = 'All'
        self.fields['lec_type'].initial = 'Lecture'

    def clean(self):
        cleaned = super().clean()
        day, start, end = cleaned.get('day'), cleaned.get('start_time'), cleaned.get('end_time')
        course, batch = cleaned.get('course'), cleaned.get('batch')
        if not (day and start and end):
            return cleaned
        if end <= start:
            self.add_error('end_time', 'The slot must end after it starts.')
            return cleaned

        overlapping = TimeTable.objects.filter(day=day, start_time__lt=end, end_time__gt=start)
        if self.instance.pk:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        for slot in overlapping.filter(cls=self.cls).select_related('course'):
            if batch == 'All' or slot.batch in ('All', batch):
                raise forms.ValidationError(
                    'This class already has %s from %s on %s.'
                    % (slot.course or 'a slot', slot.period, day))

        if course:
            teachers = set(Assign_cls.objects.filter(cls=self.cls, course=course)
                           .values_list('teacher', flat=True))
            for slot in overlapping.exclude(cls=self.cls).select_related('cls', 'course'):
                clash = (Assign_cls.objects.filter(cls=slot.cls, course=slot.course,
                                                   teacher__in=teachers)
                         .select_related('teacher__user').first())
                if clash:
                    raise forms.ValidationError(
                        '%s is already teaching %s from %s on %s.'
                        % (clash.teacher.user.full_name, slot.cls, slot.period, day))
        return cleaned
