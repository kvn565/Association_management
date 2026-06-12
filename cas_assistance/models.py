from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal

# 🔗 LIAISON AVEC TON MODULE
from twiyungunganye.models import Membre, CotisationImprevu


class CasAssistance(models.Model):

    id_assistance = models.AutoField(primary_key=True)

    membre = models.ForeignKey(
        Membre,
        on_delete=models.CASCADE,
        related_name='assistances'
    )

    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='assistances', null=True, blank=True
    )

    montant = models.DecimalField(max_digits=12, decimal_places=3)

    motif = models.TextField()

    date_assistance = models.DateField(default=timezone.now)

    cree_par = models.ForeignKey(
        Membre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assistances_creees'
    )

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cas_assistances'
        ordering = ['-date_assistance']

    def __str__(self):
        return f"{self.membre} - {self.montant} FBU"

    def clean(self):
        if not self.tenant_id:
            raise ValidationError("Le cas d'assistance doit être lié à une association (tenant).")
        qs_imprevus = CotisationImprevu.objects.filter(statut='PAYE', tenant=self.tenant)
        qs_assistance = CasAssistance.objects.exclude(pk=self.pk).filter(tenant=self.tenant)
        total_imprevus = qs_imprevus.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')
        total_assistance = qs_assistance.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')

        solde = total_imprevus - total_assistance

        if self.montant > solde:
            raise ValidationError(
                f"Solde imprévus insuffisant. Disponible : {solde} FBU"
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
