from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    # Spec §14.1 — dashboard KPIs overview
    path('', views.reporting_dashboard, name='dashboard'),

    # Spec §14.2 — fill rate per session
    path('fill-rate/', views.fill_rate_report, name='fill_rate'),

    # Spec §14.3 — operational reports
    path('by-formation/',  views.sessions_by_formation,  name='by_formation'),
    path('by-client/',     views.sessions_by_client,     name='by_client'),
    path('by-trainer/',    views.sessions_by_trainer,    name='by_trainer'),
    path('pass-rate/',     views.pass_rate_by_formation, name='pass_rate'),
    path('certificates/',  views.certificate_volume,     name='certificate_volume'),
    path('trainer-activity/', views.trainer_activity,   name='trainer_activity'),
]
