from django.contrib import admin
from .models import CasAssistance


@admin.register(CasAssistance)
class CasAssistanceAdmin(admin.ModelAdmin):

    list_display = ('membre', 'montant', 'date_assistance')
    search_fields = ('membre__nom', 'membre__prenom', 'motif')
    list_filter = ('tenant', 'date_assistance',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
