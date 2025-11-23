from datetime import time
from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Business, Day


# -------------------------
# USER REGISTRATION
# -------------------------
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=UserProfile.USER_ROLES)
    business = forms.ModelChoiceField(queryset=Business.objects.all(), required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        business = cleaned_data.get('business')
        if role == 'client' and not business:
            raise forms.ValidationError("Clients must select a business.")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                business=self.cleaned_data['business'] if self.cleaned_data['role'] == 'client' else None
            )
        return user


# -------------------------
# BUSINESS CREATION FORM
# -------------------------
class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['name', 'description']


# -------------------------
# DAY CREATION FORM
# -------------------------
from django import forms
from .models import Day

class CreateDayForm(forms.ModelForm):
    class Meta:
        model = Day
        fields = ['date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'})
        }

    def clean_date(self):
        date = self.cleaned_data['date']
        from django.utils import timezone
        if date < timezone.now().date():
            raise forms.ValidationError("Cannot create a day in the past.")
        return date



# -------------------------
# SLOT GENERATION FORM
# -------------------------
class SlotGenerationForm(forms.Form):
    start_time = forms.TimeField(
        label="Start Time",
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        initial=time(9, 0),
    )
    end_time = forms.TimeField(
        label="End Time",
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        initial=time(17, 0),
    )
    interval_minutes = forms.IntegerField(
        label="Slot Interval (minutes)",
        min_value=5,
        max_value=240,
        initial=30,
        help_text="Length of each slot in minutes",
    )
    breaks = forms.CharField(
        label="Breaks (optional)",
        required=False,
        help_text='Format: "12:00-13:00,15:00-15:15"',
    )

    def clean_breaks(self):
        data = self.cleaned_data.get("breaks")
        breaks_list = []
        if data:
            try:
                periods = data.split(",")
                for p in periods:
                    start_str, end_str = p.split("-")
                    start = time.fromisoformat(start_str.strip())
                    end = time.fromisoformat(end_str.strip())
                    if start >= end:
                        raise forms.ValidationError(f"Break start must be before end: {p}")
                    breaks_list.append((start, end))
            except Exception:
                raise forms.ValidationError("Invalid breaks format. Use HH:MM-HH:MM, separated by commas.")
        return breaks_list
