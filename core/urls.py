from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('sites.urls')),
]

# Em ambiente de desenvolvimento local (DEBUG=True), o Django serve os arquivos estáticos e mídias diretamente.
# No Render (produção), o WhiteNoise serve os estáticos e a nossa View segura gerencia o download de mídias.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
