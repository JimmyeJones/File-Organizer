from django.contrib import admin
from django.utils.html import format_html

from .models import Album, Photo


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 3
    fields = ("image", "caption", "thumbnail_preview")
    readonly_fields = ("thumbnail_preview",)

    def thumbnail_preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:60px;">', obj.image.url)
        return ""
    thumbnail_preview.short_description = "Preview"


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ("title", "photo_count", "created_at")
    search_fields = ("title",)
    inlines = [PhotoInline]

    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = "Photos"


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "album", "uploaded_at")
    list_filter = ("album",)
    search_fields = ("caption",)
