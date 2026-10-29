from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from import_export.admin import ExportMixin
from .models import GeneratedDocument, HotEvaluation
from .resources import GeneratedDocumentResource

@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(ExportMixin, admin.ModelAdmin):
    resource_classes = [GeneratedDocumentResource]
    list_display = [
        'doc_type_display', 'session_reference', 'participant_name', 
        'day_number', 'generated_at', 'generated_by', 'is_latest', 'download_link'
    ]
    list_filter = ['doc_type', 'is_latest', 'generated_at', 'day_number']
    search_fields = [
        'session__reference', 'session__formation__title',
        'participant__first_name', 'participant__last_name'
    ]
    readonly_fields = [
        'session', 'participant', 'doc_type', 'generated_at', 
        'generated_by', 'file', 'day_number'
    ]
    
    def doc_type_display(self, obj):
        return obj.get_doc_type_display()
    doc_type_display.short_description = "Type de document"
    
    def session_reference(self, obj):
        url = reverse('admin:formations_session_change', args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, obj.session.reference)
    session_reference.short_description = "Session"
    
    def participant_name(self, obj):
        if obj.participant:
            url = reverse('admin:formations_participant_change', args=[obj.participant.pk])
            return format_html('<a href="{}">{}</a>', url, obj.participant.full_name)
        return "-"
    participant_name.short_description = "Participant"
    
    def download_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">Télécharger</a>',
                obj.file.url
            )
        return "-"
    download_link.short_description = "Fichier"
    
    def has_add_permission(self, request):
        return False  # Documents are generated through views
    
    def has_change_permission(self, request, obj=None):
        return False  # Documents are immutable once generated
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete


@admin.register(HotEvaluation)
class HotEvaluationAdmin(admin.ModelAdmin):
    list_display = ["participant", "overall_satisfaction", "total_score", "filled_by", "filled_at"]
    list_filter = ["overall_satisfaction", "filled_at"]
    search_fields = ["participant__first_name", "participant__last_name"]
    readonly_fields = ["filled_by", "filled_at"]