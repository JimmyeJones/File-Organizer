from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail
from django.conf import settings

from .models import Member


def approve_members(modeladmin, request, queryset):
    for member in queryset.filter(is_approved=False):
        member.is_approved = True
        member.is_active = True
        member.save()
        send_mail(
            subject="Your HAM Club membership has been approved",
            message=(
                f"Hi {member.first_name or member.username},\n\n"
                "Your membership application has been approved. "
                "You can now log in at the club website.\n\n73 de the club admin"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email],
            fail_silently=True,
        )


approve_members.short_description = "Approve selected members"


@admin.register(Member)
class MemberAdmin(UserAdmin):
    list_display = ("username", "callsign", "email", "get_full_name", "is_approved", "is_active", "date_joined")
    list_filter = ("is_approved", "is_active", "is_staff")
    search_fields = ("username", "callsign", "email", "first_name", "last_name")
    actions = [approve_members]

    fieldsets = UserAdmin.fieldsets + (
        ("HAM Club", {"fields": ("callsign", "bio", "is_approved")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("HAM Club", {"fields": ("callsign", "bio")}),
    )
