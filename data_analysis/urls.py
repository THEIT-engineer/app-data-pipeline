from django.urls import path
from . import views

urlpatterns = [
    path("",views.index, name="index"),
    path("webscrapping",views.webscrapping, name="webscrapping"),
    path("telecharger/<str:dossier>/<str:nom>", views.telecharger, name="telecharger"),
    path("cleaning",views.cleaning, name="cleaning"),
    path("aed",views.AED, name="aed"),
    path("feeling",views.feeling_analysis, name="feeling"),
    path("visualization",views.data_vizualization, name="visualization"),

    
]