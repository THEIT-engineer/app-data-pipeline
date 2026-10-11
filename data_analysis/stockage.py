"""Enregistrement et lecture des fichiers de données produits par l'application."""
import csv
from datetime import datetime

from django.conf import settings

# Un dossier par étape du pipeline : <projet>/media/collectes/, <projet>/media/nettoyes/
DOSSIERS = {
    "collectes": settings.MEDIA_ROOT / "collectes",
    "nettoyes": settings.MEDIA_ROOT / "nettoyes",
    "sentiments": settings.MEDIA_ROOT / "sentiments",
}
DOSSIER_COLLECTES = DOSSIERS["collectes"]


def enregistrer_csv(colonnes, lignes):
    """Écrit les données dans un nouveau fichier CSV et renvoie son chemin."""
    DOSSIER_COLLECTES.mkdir(parents=True, exist_ok=True)
    # Un nom unique par collecte, daté : collecte_20261011_143205.csv
    nom = f"collecte_{datetime.now():%Y%m%d_%H%M%S}.csv"
    chemin = DOSSIER_COLLECTES / nom
    # utf-8-sig : Excel affiche alors correctement les accents et le symbole £
    with open(chemin, "w", newline="", encoding="utf-8-sig") as fichier:
        writer = csv.writer(fichier)
        writer.writerow(colonnes)   # ligne d'en-tête
        writer.writerows(lignes)    # une ligne par élément collecté
    return chemin


def lister(dossier):
    """Noms des fichiers CSV d'un dossier ("collectes" ou "nettoyes"), du plus récent au plus ancien."""
    base = DOSSIERS[dossier]
    if not base.exists():
        return []
    return sorted((f.name for f in base.glob("*.csv")), reverse=True)


def lister_collectes():
    return lister("collectes")


def enregistrer_nettoye(df, nom_source):
    """Enregistre un DataFrame nettoyé : collecte_X.csv -> nettoye_collecte_X.csv (remplacé à chaque nettoyage)."""
    dossier = DOSSIERS["nettoyes"]
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"nettoye_{nom_source}"
    df.to_csv(chemin, index=False, encoding="utf-8-sig")  # index=False : pas de colonne 0, 1, 2…
    return chemin


def enregistrer_sentiments(df, nom_source):
    """nettoye_X.csv -> sentiments_X.csv, dans media/sentiments/."""
    dossier = DOSSIERS["sentiments"]
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"sentiments_{nom_source.removeprefix('nettoye_')}"
    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    return chemin


def chemin_fichier(dossier, nom):
    """Renvoie le chemin du fichier `nom` s'il existe DANS l'un des dossiers connus, sinon None.

    Protège contre les noms du type "../settings.py" qui permettraient de
    télécharger n'importe quel fichier du serveur.
    """
    base = DOSSIERS.get(dossier)
    if base is None:
        return None
    chemin = (base / nom).resolve()
    if chemin.parent != base.resolve() or not chemin.is_file():
        return None
    return chemin


def chemin_collecte(nom):
    return chemin_fichier("collectes", nom)
