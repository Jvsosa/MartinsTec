from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.site_list, name='site_list'),
    path('site/<int:pk>/', views.site_detail, name='site_detail'),
    path('site/delete/<int:pk>/', views.delete_site, name='delete_site'),
    path('file/download/<int:file_id>/', views.download_file, name='download_file'),
    path('file/delete/<int:file_id>/', views.delete_file, name='delete_file'),
]
