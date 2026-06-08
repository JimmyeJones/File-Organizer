from django.contrib.auth.models import AbstractUser
from django.db import models


class Member(AbstractUser):
    callsign = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        display = self.get_full_name() or self.username
        if self.callsign:
            return f"{display} ({self.callsign})"
        return display
