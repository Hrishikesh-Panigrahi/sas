from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm

from sas.forms import BootstrapFormMixin
from users.models import User


class UserAccountForm(BootstrapFormMixin, forms.ModelForm):
    """Name, email and password for a new or existing account.

    A password is required when creating an account. When editing, the
    password fields are optional and only change the password if filled in.
    """
    password1 = forms.CharField(
        label='Password', strip=False, required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label='Confirm password', strip=False, required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'name@college.edu'}),
        }

    def __init__(self, *args, dept=None, **kwargs):
        # `dept` is the creator's department. Without one (a superuser), the
        # department becomes a field on the form instead.
        self.dept = dept
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        if self.instance.pk is None:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
        else:
            self.fields['password1'].label = 'New password'
            self.fields['password1'].help_text = 'Leave both fields blank to keep the current password.'
        if not dept:
            self.fields['department'] = forms.ChoiceField(
                choices=[('', 'Select a department')] + User.department_choices,
                initial=self.instance.department,
                widget=forms.Select(attrs={'class': 'custom-select'}),
            )

    def clean_email(self):
        return self.cleaned_data['email'].strip()

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if (p1 or p2) and p1 != p2:
            raise forms.ValidationError("The two passwords don't match.")
        return p2

    def _post_clean(self):
        super()._post_clean()
        # Validate after the instance has the new name/email, so the
        # "too similar to your name" check sees them.
        password = self.cleaned_data.get('password2')
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password2', error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.department = self.dept or self.cleaned_data.get('department') or user.department
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class TeacherForm(UserAccountForm):
    class Meta(UserAccountForm.Meta):
        fields = ['first_name', 'last_name', 'email', 'is_classteacher']
        labels = {'is_classteacher': 'Can be a class teacher'}
        help_texts = {'is_classteacher': 'Class teachers can manage classes and students.'}

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            user.save()
        return user


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'middle_name', 'last_name']


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass
