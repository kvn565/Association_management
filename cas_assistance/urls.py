from django.urls import path
from .views import liste_assistance, creer_assistance, modifier_assistance, supprimer_assistance, rapport_assistance_pdf

app_name = 'cas_assistance'

urlpatterns = [
    path('', liste_assistance, name='liste'),
    path('ajouter/', creer_assistance, name='ajouter'),
    path('modifier/<int:pk>/', modifier_assistance, name='modifier'),
    path('supprimer/<int:pk>/', supprimer_assistance, name='supprimer'),
    path('rapport/<int:mois>/<int:annee>/', rapport_assistance_pdf, name='rapport_pdf'),
]
