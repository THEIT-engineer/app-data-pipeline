"""Fonctions de nettoyage de données avec pandas, indépendantes de Django."""
import pandas as pd


def resume(df):
    """Trois chiffres qui résument la qualité d'un DataFrame."""
    return {
        "rows": len(df),
        "missing": int(df.isna().sum().sum()),   # nombre total de cases vides
        "duplicates": int(df.duplicated().sum()),  # lignes identiques à une ligne précédente
    }


def profil_colonnes(df):
    """Pour chaque colonne : son type pandas, ses valeurs manquantes et son taux de complétude."""
    profil = []
    for col in df.columns:
        manquantes = int(df[col].isna().sum())
        profil.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "missing": manquantes,
            "complete": round(100 * (1 - manquantes / len(df)), 1) if len(df) else 0,
        })
    return profil


def apercu(df, n=20):
    """Les n premières lignes, prêtes pour le template (NaN remplacés par None)."""
    debut = df.head(n)
    return debut.astype(object).where(debut.notna(), None).values.tolist()


# ---------------------------------------------------------------------------
# Opérations sur UNE colonne : chacune reçoit une Series et renvoie une Series
# ---------------------------------------------------------------------------

def retirer_extrait_repete(texte, n=50):
    """"Début tronqué… Début complet" -> "Début complet".

    Si les n premiers caractères réapparaissent plus loin, tout ce qui précède
    cette 2e occurrence n'était qu'un extrait : on le retire.
    """
    if pd.isna(texte) or len(texte) < 2 * n:
        return texte
    position = texte.find(texte[:n], 1)  # on cherche à partir du 2e caractère
    return texte[position:] if position != -1 else texte


def en_texte(serie):
    """Texte propre : espaces superflus, suffixe « ...more » et extrait répété retirés ; vide -> manquant."""
    texte = serie.astype("string").str.strip()
    texte = texte.str.replace(r"\s*\.\.\.\s*more$", "", regex=True)  # "…blabla ...more" -> "…blabla"
    texte = texte.str.replace(r"\s+", " ", regex=True)               # espaces multiples -> un seul
    texte = texte.map(retirer_extrait_repete).astype("string")
    return texte.replace("", pd.NA)


def en_nombre(serie):
    """Extrait le premier nombre du texte : "£51.77" -> 51.77, "In stock (22 available)" -> 22."""
    nombre = serie.astype("string").str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    return pd.to_numeric(nombre, errors="coerce")  # ce qui n'est pas un nombre devient NaN


CHIFFRES_EN_MOTS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}


def en_note(serie):
    """Note écrite en mots -> entier : "star-rating Three" -> 3."""
    dernier_mot = serie.astype("string").str.strip().str.split().str[-1].str.lower()
    return pd.to_numeric(dernier_mot.replace(CHIFFRES_EN_MOTS), errors="coerce").astype("Int64")


def en_categorie(serie):
    """Peu de valeurs différentes qui se répètent -> type category (plus léger, plus clair)."""
    return en_texte(serie).astype("category")


# Regroupement des 50 catégories de books.toscrape.com en 7 genres.
# C'est un choix d'analyse : modifiez-le librement.
GENRES_LIVRES = {
    "Romans": ["Fiction", "Classics", "Romance", "Mystery", "Thriller", "Suspense", "Crime", "Horror",
               "Fantasy", "Science Fiction", "Paranormal", "Historical Fiction", "Historical",
               "Womens Fiction", "Adult Fiction", "New Adult", "Christian Fiction", "Contemporary",
               "Short Stories", "Novels", "Erotica"],
    "Jeunesse": ["Childrens", "Young Adult"],
    "BD, arts & poésie": ["Sequential Art", "Art", "Music", "Poetry", "Humor"],
    "Savoirs & documents": ["Nonfiction", "History", "Science", "Philosophy", "Psychology", "Politics",
                            "Cultural", "Academic", "Business", "Biography", "Autobiography"],
    "Religion & spiritualité": ["Religion", "Christian", "Spirituality"],
    "Vie pratique": ["Food and Drink", "Travel", "Health", "Self Help", "Parenting", "Sports and Games"],
    "Non classé": ["Default", "Add a comment"],  # fausses catégories du site
}
# Inversion du dictionnaire : {"Fiction": "Romans", "Classics": "Romans", ...}
GENRE_DE = {categorie: genre for genre, categories in GENRES_LIVRES.items() for categorie in categories}


def en_genre(serie):
    """Catégorie détaillée -> genre ; une catégorie inconnue devient « Autre »."""
    return en_texte(serie).map(GENRE_DE).fillna("Autre").astype("category")


OPERATIONS = {
    "texte": en_texte,
    "nombre": en_nombre,
    "note": en_note,
    "categorie": en_categorie,
}


def appliquer(df, choix, noms):
    """Applique à chaque colonne l'opération choisie, puis la renomme.

    choix : {"prix": "nombre", "stock": "supprimer", ...}
    noms  : {"stock.1": "quantite", ...}  (nouveaux noms ; absent = nom inchangé)
    Renvoie le DataFrame nettoyé et un journal de ce qui s'est passé.
    """
    df = df.copy()  # on ne modifie jamais l'original
    journal = []
    for col, operation in choix.items():
        if operation == "supprimer":
            df = df.drop(columns=col)
            journal.append(f"« {col} » supprimée")
            continue
        if operation == "genre":
            df[col] = en_categorie(df[col])
            df["genre"] = en_genre(df[col])
            journal.append(f"« {col} » -> category, et nouvelle colonne « genre » ({df['genre'].nunique()} genres)")
            continue
        if operation in OPERATIONS:
            remplies_avant = int(df[col].notna().sum())
            df[col] = OPERATIONS[operation](df[col])
            perdues = remplies_avant - int(df[col].notna().sum())
            message = f"« {col} » -> {df[col].dtype}"
            if perdues:
                message += f" ({perdues} valeurs non convertibles devenues vides)"
            journal.append(message)
    df = df.rename(columns={ancien: nouveau for ancien, nouveau in noms.items() if ancien in df.columns})
    return df, journal
