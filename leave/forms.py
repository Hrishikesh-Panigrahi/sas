import datetime

from django import forms
from django.utils import timezone

from sas.forms import BootstrapFormMixin
from .models import LeaveRequest

MAX_DOCUMENT = 2 * 1024 * 1024
DOCUMENT_TYPES = {'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png'}


class LeaveForm(BootstrapFormMixin, forms.ModelForm):
    document_file = forms.FileField(
        label='Supporting document', required=False,
        help_text='Optional. PDF, JPG or PNG up to 2 MB, such as a medical certificate.')

    class Meta:
        model = LeaveRequest
        fields = ['kind', 'start_date', 'end_date', 'reason']
        labels = {'kind': 'Type of leave', 'start_date': 'From', 'end_date': 'To'}
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'A sentence or two for your class teacher.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document_file'].widget.attrs.update(
            {'class': 'form-control-file', 'accept': ','.join(DOCUMENT_TYPES.values())})
        self.fields['start_date'].initial = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end:
            if end < start:
                self.add_error('end_date', 'The leave has to end on or after the day it starts.')
            elif (end - start).days > 30:
                self.add_error('end_date', 'Leave can cover at most 31 days; split longer leave into parts.')
            if start < timezone.localdate() - datetime.timedelta(days=60):
                self.add_error('start_date', 'Leave can be requested up to 60 days after the fact.')
        return cleaned

    def clean_document_file(self):
        f = self.cleaned_data.get('document_file')
        if not f:
            return f
        if f.size > MAX_DOCUMENT:
            raise forms.ValidationError('That file is larger than 2 MB.')
        ext = '.' + f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
        allowed = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}
        if ext not in allowed:
            raise forms.ValidationError('Upload a PDF, JPG or PNG file.')
        head = f.read(8)
        f.seek(0)
        signature_ok = (head.startswith(b'%PDF') if ext == '.pdf' else
                        head.startswith(b'\xff\xd8') if ext in ('.jpg', '.jpeg') else
                        head.startswith(b'\x89PNG'))
        if not signature_ok:
            raise forms.ValidationError("That file doesn't look like a real %s." % ext[1:].upper())
        f.sas_type = allowed[ext]
        return f

    def save(self, student, commit=True):
        leave = super().save(commit=False)
        leave.student = student
        f = self.cleaned_data.get('document_file')
        if f:
            leave.document = f.read()
            leave.document_name = f.name[-200:]
            leave.document_type = f.sas_type
        if commit:
            leave.save()
        return leave
