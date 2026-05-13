from django.shortcuts import get_object_or_404, render

from .models import Album


def album_list(request):
    albums = Album.objects.prefetch_related("photos")
    return render(request, "gallery/album_list.html", {"albums": albums})


def album_detail(request, pk):
    album = get_object_or_404(Album, pk=pk)
    photos = album.photos.all()
    return render(request, "gallery/album_detail.html", {"album": album, "photos": photos})
