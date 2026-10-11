"""Construction de graphiques Plotly à partir des choix du formulaire, indépendante de Django."""
import pandas as pd
import plotly.express as px

from .exploration import MISE_EN_PAGE

PALETTE = ["#3b5bdb", "#12805c", "#c4314b", "#a8590b", "#0f6f94", "#7048e8", "#5c677d", "#d6336c"]
# Couleurs fixes pour les sentiments : un négatif est toujours rouge, quel que soit le graphique
COULEURS_SENTIMENT = {"positive": "#12805c", "neutral": "#8189a3", "negative": "#c4314b"}

LIBELLES_AGREGATION = {"sum": "somme", "mean": "moyenne", "median": "médiane", "count": "nombre"}


def agreger(df, x, y, couleur, agregation):
    """Une ligne par valeur de x (et de couleur) : l'effectif, ou y agrégé (somme, moyenne…)."""
    # Si la couleur est la même colonne que x, on ne groupe qu'une fois (sinon pandas crée deux colonnes "genre")
    groupes = [x] + ([couleur] if couleur and couleur != x else [])
    if not y or agregation == "count":
        table = df.groupby(groupes, observed=True).size().reset_index(name="effectif")
        return table, "effectif"
    table = df.groupby(groupes, observed=True)[y].agg(agregation).round(2).reset_index()
    return table, y


def construire(df, type_graphique, x, y="", couleur="", agregation="mean", titre=""):
    """Renvoie une figure Plotly, ou lève ValueError avec un message compréhensible."""
    for col in (x, y, couleur):
        if col and col not in df.columns:
            raise ValueError(f"La colonne « {col} » n'existe pas dans ce fichier.")
    if not x:
        raise ValueError("Choisissez une colonne pour l'axe X.")

    options = {"color": couleur or None, "color_discrete_sequence": PALETTE}
    ordres = {}  # ordre d'affichage des catégories, complété par chaque type de graphique
    if couleur == "sentiment":
        options["color_discrete_map"] = COULEURS_SENTIMENT
        ordres["sentiment"] = list(COULEURS_SENTIMENT)  # positif, neutre, négatif

    if type_graphique in ("bar", "line"):
        table, valeur = agreger(df, x, y, couleur, agregation)
        if type_graphique == "bar":
            if pd.api.types.is_numeric_dtype(table[x]):
                ordre = sorted(table[x].unique())  # une note 1..5 garde son ordre naturel
            else:
                # Catégories triées de la plus petite à la plus grande : la comparaison saute aux yeux
                ordre = table.groupby(x, observed=True)[valeur].sum().sort_values().index
            ordre = [str(v) for v in ordre]
            table[x] = table[x].astype(str)
            fig = px.bar(table, x=x, y=valeur, category_orders={**ordres, x: ordre}, text_auto=True, **options)
        else:
            fig = px.line(table.sort_values(x), x=x, y=valeur, markers=True, category_orders=ordres, **options)
        if y and agregation != "count":
            fig.update_yaxes(title=f"{y} ({LIBELLES_AGREGATION[agregation]})")

    elif type_graphique == "scatter":
        if not y:
            raise ValueError("Le nuage de points a besoin d'une variable numérique en Y.")
        survol = "titre" if "titre" in df.columns else None
        fig = px.scatter(df, x=x, y=y, hover_name=survol, opacity=0.75, category_orders=ordres, **options)

    elif type_graphique == "box":
        if not y:
            raise ValueError("La boîte à moustaches a besoin d'une variable numérique en Y.")
        # Boîtes triées par médiane croissante
        ordre = df.groupby(x, observed=True)[y].median().sort_values().index.astype(str).tolist()
        donnees = df.assign(**{x: df[x].astype(str)})
        fig = px.box(donnees, x=x, y=y, points="all", category_orders={**ordres, x: ordre},
                     hover_name="titre" if "titre" in df.columns else None, **options)

    elif type_graphique == "pie":
        table, valeur = agreger(df, x, y, "", agregation)
        fig = px.pie(table, names=x, values=valeur, hole=0.45, color_discrete_sequence=PALETTE,
                     color=x if x == "sentiment" else None, color_discrete_map=COULEURS_SENTIMENT)

    elif type_graphique == "heatmap":
        if not couleur or couleur == x:
            raise ValueError("La heatmap croise deux catégories différentes : choisissez la seconde dans « Couleur par ».")
        table, valeur = agreger(df, x, y, couleur, agregation)
        matrice = table.pivot(index=couleur, columns=x, values=valeur)
        fig = px.imshow(matrice, text_auto=True, aspect="auto", color_continuous_scale="Blues")

    else:
        raise ValueError("Type de graphique inconnu.")

    fig.update_layout(**dict(MISE_EN_PAGE, height=460, title=None, legend_title_text=couleur or None))
    return fig


def en_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displaylogo": False, "responsive": True})


# Graphiques suggérés : ils répondent aux questions posées pendant le pipeline.
# Chacun n'est proposé que si le fichier contient les colonnes nécessaires.
SUGGESTIONS = [
    {"label": "Ton des descriptions par genre", "chart_type": "box", "x": "genre", "y": "sentiment_score",
     "title": "Score de sentiment des descriptions, par genre"},
    {"label": "Sentiments par genre (effectifs)", "chart_type": "bar", "x": "genre", "color": "sentiment",
     "title": "Nombre de descriptions positives, neutres et négatives par genre"},
    {"label": "Prix médian par genre", "chart_type": "bar", "x": "genre", "y": "prix", "agg": "median",
     "title": "Prix médian par genre (£)"},
    {"label": "Répartition des notes", "chart_type": "bar", "x": "note", "title": "Nombre de livres par note"},
    {"label": "Note et sentiment", "chart_type": "scatter", "x": "note", "y": "sentiment_score", "color": "genre",
     "title": "La note des lecteurs suit-elle le ton de la description ?"},
    {"label": "Part de chaque genre", "chart_type": "pie", "x": "genre", "title": "Part de chaque genre"},
]


def suggestions_pour(df):
    utiles = []
    for s in SUGGESTIONS:
        colonnes = [s.get("x"), s.get("y"), s.get("color")]
        if all(c in df.columns for c in colonnes if c):
            utiles.append(s)
    return utiles
