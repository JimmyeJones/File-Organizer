from django import forms

from .models import PresentationSlot


class ClaimSlotForm(forms.ModelForm):
    class Meta:
        model = PresentationSlot
        fields = ("topic", "description")
        widgets = {
            "topic": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your presentation topic"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
