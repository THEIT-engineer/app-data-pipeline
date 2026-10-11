"""Fonctions de web scraping, indépendantes de Django.

Les vues appellent ces fonctions ; elles ne savent rien des requêtes HTTP de
l'utilisateur ni des templates, ce qui permet de les tester séparément.
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def lire_champs(texte):
    """Transforme le texte du formulaire en liste de champs à extraire.

    "titre: h3 a@title"  ->  ("titre", "h3 a", "title")
    "prix: p.price_color" ->  ("prix", "p.price_color", "")
    """
    champs = []
    for ligne in texte.splitlines():
        if ":" not in ligne:
            continue  # ligne vide ou mal écrite : on l'ignore
        nom, reste = ligne.split(":", 1)
        selecteur, _, attribut = reste.partition("@")
        champs.append((nom.strip(), selecteur.strip(), attribut.strip()))
    return champs


def lire_valeur(bloc, selecteur, attribut, url_page):
    """Lit une valeur dans `bloc` : le texte d'un élément, ou l'un de ses attributs."""
    # Sans sélecteur (ex. "note: @class"), on lit le bloc lui-même
    element = bloc.select_one(selecteur) if selecteur else bloc
    if element is None:
        return None
    if not attribut:
        return element.get_text(strip=True)
    valeur = element.get(attribut)
    if isinstance(valeur, list):  # l'attribut class est une liste
        return " ".join(valeur)
    if attribut in ("href", "src") and valeur:
        # Liens et images relatifs ("catalogue/…") -> adresse complète
        return urljoin(url_page, valeur)
    return valeur


def extraire(html, container, champs, url_page):
    """Extrait une ligne de données par élément `container` trouvé dans le HTML."""
    soup = BeautifulSoup(html, "html.parser")
    return [
        [lire_valeur(bloc, selecteur, attribut, url_page) for _nom, selecteur, attribut in champs]
        for bloc in soup.select(container)
    ]


def extraire_page(html, champs, url_page):
    """Extrait UNE ligne de valeurs depuis une page entière (page de détail)."""
    soup = BeautifulSoup(html, "html.parser")
    return [lire_valeur(soup, selecteur, attribut, url_page) for _nom, selecteur, attribut in champs]


def page_suivante(html, url_actuelle, selecteur):
    """Renvoie l'adresse complète de la page suivante, ou None s'il n'y en a pas."""
    soup = BeautifulSoup(html, "html.parser")
    lien = soup.select_one(selecteur)
    if lien is None or not lien.get("href"):
        return None
    # Le lien est relatif ("page-2.html") : on le complète à partir de l'adresse actuelle
    return urljoin(url_actuelle, lien["href"])
