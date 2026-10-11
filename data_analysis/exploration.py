"""Analyse exploratoire (AED) avec pandas et Plotly, indépendante de Django."""
import pandas as pd
import plotly.express as px

# Au-delà de ce nombre de valeurs différentes, une colonne de texte n'est jamais
# traitée comme une catégorie (le graphique en barres serait illisible).
MAX_MODALITES = 60

COULEUR = "#3b5bdb"
MISE_EN_PAGE = dict(
    height=340,
    margin=dict(l=40, r=20, t=10, b=40),
    paper_bgcolor="rgba(0,0,0,0)",  # fond transparent : s'adapte au thème clair/sombre
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#8189a3"),
)


def types_de_colonnes(df):
    """Sépare les colonnes en numériques, catégorielles et texte libre."""
    numeriques = list(df.select_dtypes("number").columns)
    autres = [c for c in df.columns if c not in numeriques]
    # Catégorie = peu de valeurs différentes ET qui se répètent (sinon c'est un identifiant : titre, lien)
    categorielles = [c for c in autres
                     if df[c].nunique() <= MAX_MODALITES and (df[c].nunique() <= 10 or df[c].nunique() <= len(df) / 2)]
    texte = [c for c in autres if c not in categorielles]
    return numeriques, categorielles, texte


def vue_ensemble(df, numeriques, categorielles):
    cases = df.shape[0] * df.shape[1]
    return {
        "rows": len(df),
        "columns": df.shape[1],
        "numeric": len(numeriques),
        "categorical": len(categorielles),
        "missing_pct": round(100 * df.isna().sum().sum() / cases, 1) if cases else 0,
        "memory": f"{df.memory_usage(deep=True).sum() / 1024:.0f} Ko",
    }


def statistiques(df, numeriques):
    """Tableau des statistiques descriptives : une ligne par variable numérique."""
    if not numeriques:
        return None
    stats = df[numeriques].describe().T  # .T : on transpose pour avoir une ligne par variable
    entetes = {"count": "effectif", "mean": "moyenne", "std": "écart-type", "min": "min",
               "25%": "Q1 (25 %)", "50%": "médiane", "75%": "Q3 (75 %)", "max": "max"}
    lignes = [[nom] + [round(float(v), 2) for v in valeurs] for nom, valeurs in stats.iterrows()]
    return {"columns": ["variable"] + [entetes[c] for c in stats.columns], "rows": lignes}


def manquants(df):
    """Les colonnes qui ont des valeurs manquantes, de la plus touchée à la moins touchée."""
    resultat = []
    for col, n in df.isna().sum().sort_values(ascending=False).items():
        if n:
            resultat.append({"name": col, "count": int(n), "pct": round(100 * n / len(df), 1)})
    return resultat


def graphiques(df, numeriques, categorielles):
    """Un histogramme par variable numérique, un diagramme en barres par catégorie, et les corrélations."""
    figures = []
    for col in numeriques:
        fig = px.histogram(df, x=col, nbins=20, color_discrete_sequence=[COULEUR])
        fig.update_layout(bargap=0.05, yaxis_title="nombre de livres", **MISE_EN_PAGE)
        figures.append((f"Distribution de « {col} »", fig))
    for col in categorielles:
        effectifs = df[col].value_counts().sort_values()
        fig = px.bar(x=effectifs.values, y=effectifs.index.astype(str), orientation="h",
                     color_discrete_sequence=[COULEUR], labels={"x": "nombre de livres", "y": ""})
        fig.update_layout(**dict(MISE_EN_PAGE, height=max(240, 24 * len(effectifs) + 60)))
        figures.append((f"Répartition par « {col} »", fig))
    if len(numeriques) >= 2:
        correlation = df[numeriques].corr().round(2)
        fig = px.imshow(correlation, text_auto=True, zmin=-1, zmax=1, color_continuous_scale="RdBu_r")
        fig.update_layout(**MISE_EN_PAGE)
        figures.append(("Corrélations entre variables numériques", fig))
    return [
        {"title": titre, "html": fig.to_html(full_html=False, include_plotlyjs=False,
                                             config={"displaylogo": False, "responsive": True})}
        for titre, fig in figures
    ]


def observations(df, numeriques, categorielles):
    """Quelques constats automatiques, à vérifier ensuite sur les graphiques."""
    constats = []
    for col in numeriques:
        serie = df[col].dropna()
        if serie.nunique() <= 1:
            constats.append({"level": "warning", "text": f"« {col} » ne prend qu'une seule valeur : elle n'apporte aucune information."})
            continue
        asymetrie = serie.skew()
        if abs(asymetrie) > 1:
            sens = "vers les grandes valeurs" if asymetrie > 0 else "vers les petites valeurs"
            constats.append({"level": "warning", "text": f"« {col} » est asymétrique ({asymetrie:.2f}), étirée {sens} : préférez la médiane à la moyenne."})
        q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
        ecart = q3 - q1
        aberrantes = int(((serie < q1 - 1.5 * ecart) | (serie > q3 + 1.5 * ecart)).sum())
        if aberrantes:
            constats.append({"level": "info", "text": f"« {col} » : {aberrantes} valeur(s) hors de [Q1 − 1,5×IQR ; Q3 + 1,5×IQR] (méthode IQR)."})
    if len(numeriques) >= 2:
        correlation = df[numeriques].corr()
        for i, a in enumerate(numeriques):
            for b in numeriques[i + 1:]:
                r = correlation.loc[a, b]
                if abs(r) >= 0.3:
                    force = "forte" if abs(r) >= 0.7 else "modérée"
                    constats.append({"level": "info", "text": f"Corrélation {force} entre « {a} » et « {b} » (r = {r:.2f})."})
    for col in categorielles:
        part = df[col].value_counts(normalize=True)
        if len(part) and part.iloc[0] >= 0.2:
            constats.append({"level": "info", "text": f"« {col} » : « {part.index[0]} » représente {100 * part.iloc[0]:.0f} % des lignes."})
    for m in manquants(df):
        if m["pct"] >= 5:
            constats.append({"level": "danger", "text": f"« {m['name']} » : {m['pct']} % de valeurs manquantes."})
    return constats


def analyser(df):
    """Tout ce dont la page AED a besoin, en un seul dictionnaire."""
    numeriques, categorielles, texte = types_de_colonnes(df)
    return {
        "overview": vue_ensemble(df, numeriques, categorielles),
        "describe": statistiques(df, numeriques),
        "missing": manquants(df),
        "charts": graphiques(df, numeriques, categorielles),
        "insights": observations(df, numeriques, categorielles),
        "colonnes_texte": texte,
    }
