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
    path('calendar/events/', views.calendar_events_api, name='calendar_events_api'),
    path('calendar/note/add/', views.add_calendar_note, name='add_calendar_note'),
    path('calendar/note/edit/', views.edit_calendar_note, name='edit_calendar_note'),
    path('calendar/note/delete/', views.delete_calendar_note, name='delete_calendar_note'),
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('profile/', views.user_profile, name='user_profile'),
    path('settings/', views.user_settings, name='user_settings'),
    path('logs/', views.system_logs, name='system_logs'),
    path('help/', views.help_center, name='help_center'),
]
