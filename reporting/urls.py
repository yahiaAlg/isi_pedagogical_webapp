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

    # Spec §14.4 — costs & resource utilization (business decisions)
    path('costs-utilization/', views.cost_utilization_report, name='cost_utilization'),

    # Spec §14.5-14.7 — additional business/infographic reports
    path('clients/',    views.client_activity_report, name='client_activity'),
    path('rooms/',      views.room_utilization_report, name='room_utilization'),
    path('trends/',     views.activity_trends_report,  name='activity_trends'),
]
