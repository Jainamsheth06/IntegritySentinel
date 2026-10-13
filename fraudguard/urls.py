from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.contrib.staticfiles.views import serve as static_serve
from django.views.static import serve as media_serve
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('arrestor/', include('arrestor.urls')),
    path('account/', include('account.urls')),
    path('', include('account.urls')),
    path('', include('detector.urls')),
    re_path(r'^static/(?P<path>.*)$', static_serve, {'insecure': True}),
    re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
]



