from django import forms
from django.utils import timezone

from sas.forms import BootstrapFormMixin
from timetable.models import TimeTable
from .models import time_slots


class LectureForm(BootstrapFormMixin, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    period = forms.ChoiceField(label='Time')

    def __init__(self, *args, assign, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['date'].initial = today
        self.fields['date'].widget.attrs['max'] = today.isoformat()

        # Offer this course's timetable times first, then the standard slots.
        slots = TimeTable.objects.filter(cls=assign.cls, course=assign.course).order_by('start_time')
        timetable = []
        for slot in slots:
            if slot.period not in timetable:
                timetable.append(slot.period)
            if slot.day == today.strftime('%A'):
                self.fields['period'].initial = slot.period
        standard = [value for value, _ in time_slots if value not in timetable]
        choices = []
        if timetable:
            choices.append(('From the timetable', [(p, p) for p in timetable]))
        choices.append(('Standard slots', [(p, p) for p in standard]))
        self.fields['period'].choices = choices

    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError("Attendance can't be taken for a future date.")
        return date
