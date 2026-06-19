from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.site_list, name='site_list'),
    path('site/<int:pk>/', views.site_detail, name='site_detail'),
    path('file/download/<int:file_id>/', views.download_file, name='download_file'),
]
