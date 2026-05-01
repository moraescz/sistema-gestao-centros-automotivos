from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from cadastros.views import custom_404_view

urlpatterns = [
    path('admin/', admin.site.urls),
    # Inclui todas as rotas da sua aplicação 'cadastros'
    path('', include('cadastros.urls')),
]

handler404 = custom_404_view

# Configuração para servir ficheiros de mídia durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns.append(re_path(r'^.*$', custom_404_view))