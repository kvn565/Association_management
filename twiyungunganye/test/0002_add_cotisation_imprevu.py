# Generated migration file
# Ajoutez ce fichier dans votre dossier migrations/

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        # Remplacez par votre dernière migration existante
        ('votre_app', 'XXXX_derniere_migration'),
    ]

    operations = [
        # Ajouter le nouveau modèle CotisationImprevu
        migrations.CreateModel(
            name='CotisationImprevu',
            fields=[
                ('id_cotisation_imprevu', models.AutoField(primary_key=True, serialize=False)),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10)),
                ('mois', models.IntegerField()),
                ('annee', models.IntegerField()),
                ('date_paiement', models.DateField(default=django.utils.timezone.now)),
                ('statut', models.CharField(choices=[('PAYE', 'Payé'), ('EN_ATTENTE', 'En attente'), ('RETARD', 'En retard')], default='EN_ATTENTE', max_length=20)),
                ('remarque', models.TextField(blank=True, null=True)),
                ('membre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cotisations_imprevus', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Cotisation Imprévus',
                'verbose_name_plural': 'Cotisations Imprévus',
                'db_table': 'cotisations_imprevus',
                'ordering': ['-annee', '-mois'],
            },
        ),
        
        # Ajouter la contrainte unique
        migrations.AlterUniqueTogether(
            name='cotisationimprevu',
            unique_together={('membre', 'mois', 'annee')},
        ),
        
        # Ajouter le nouveau champ à Association
        migrations.AddField(
            model_name='association',
            name='montant_cotisation_imprevu_mensuelle',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Montant mensuel pour les cotisations imprévus/cas sociaux', max_digits=10),
        ),
    ]
