import time

import pandas as pd
import requests
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse

from . import exploration, nettoyage, scraping, sentiments, stockage, visualisation

# En-têtes HTTP envoyés avec chaque requête : sans eux, beaucoup de sites
# reconnaissent immédiatement un script Python et refusent de répondre.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def index(request):
    return render(request, "data_analysis/index.html")


def webscrapping(request):
    context = {}

    if request.method == "POST":
        # 1. Lire les champs du formulaire (clés = attributs name="..." du HTML)
        form_data = {
            "url": request.POST.get("url", "").strip(),
            "container": request.POST.get("container", "").strip(),
            "fields": request.POST.get("fields", "").strip(),
            "next": request.POST.get("next", "").strip(),
            "detail_link": request.POST.get("detail_link", "").strip(),
            "detail_fields": request.POST.get("detail_fields", "").strip(),
            "pages": request.POST.get("pages", "1"),
            "delay": request.POST.get("delay", "1"),
        }

        # 2. Afficher dans le terminal pour vérifier ce qui arrive
        print("Formulaire reçu :", form_data)

        # 3. Renvoyer les valeurs au template pour que le formulaire reste rempli
        context["form_data"] = form_data

        # 4. Vérifier les paramètres AVANT de contacter le site
        champs = scraping.lire_champs(form_data["fields"])
        if not form_data["container"] or not champs:
            messages.warning(request, "Indiquez le sélecteur d'un élément et au moins un champ à extraire.")
            return render(request, "data_analysis/webscrapping.html", context)
        try:
            nb_pages = min(max(int(form_data["pages"]), 1), 50)  # entre 1 et 50
            delai = max(float(form_data["delay"]), 0)
        except ValueError:
            messages.error(request, "Pages et délai doivent être des nombres.")
            return render(request, "data_analysis/webscrapping.html", context)

        # 5. Boucle : télécharger, extraire, passer à la page suivante
        url = form_data["url"]
        toutes_les_lignes = []
        logs = []
        pages_lues = 0
        debut = time.time()

        while url and pages_lues < nb_pages:
            if pages_lues > 0:
                time.sleep(delai)  # politesse : on n'inonde pas le serveur
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
            except requests.RequestException as erreur:
                messages.error(request, f"Impossible de joindre {url} : {erreur}")
                break
            if response.status_code != 200 or not response.content:
                messages.warning(
                    request,
                    f"{url} a répondu avec le code {response.status_code} et une page de "
                    f"{len(response.content)} octets : collecte arrêtée (le site bloque peut-être les robots).",
                )
                break

            # response.content (octets) et non response.text : BeautifulSoup
            # détecte lui-même l'encodage réel de la page
            lignes = scraping.extraire(response.content, form_data["container"], champs, url)
            toutes_les_lignes.extend(lignes)
            pages_lues += 1
            logs.append({"level": "ok" if lignes else "warn",
                         "text": f"Page {pages_lues} : {len(lignes)} éléments ({url})"})

            url = scraping.page_suivante(response.content, url, form_data["next"]) if form_data["next"] else None

        colonnes = [nom for nom, _sel, _attr in champs]

        # 5 bis. Pages de détail : ouvrir le lien de chaque ligne et y lire d'autres champs
        champs_detail = scraping.lire_champs(form_data["detail_fields"])
        if form_data["detail_link"] and champs_detail and toutes_les_lignes:
            noms_en_double = set(colonnes) & {nom for nom, _sel, _attr in champs_detail}
            if form_data["detail_link"] not in colonnes:
                messages.warning(request, f"« {form_data['detail_link']} » n'est pas une colonne extraite : pages de détail ignorées.")
            elif noms_en_double:
                messages.warning(request, f"Colonnes en double {sorted(noms_en_double)} : renommez-les (ex. stock_detail). Pages de détail ignorées.")
            elif len(toutes_les_lignes) > 200:
                messages.warning(request, f"{len(toutes_les_lignes)} éléments : trop pour les pages de détail (maximum 200).")
            else:
                position_lien = colonnes.index(form_data["detail_link"])
                vides = [None] * len(champs_detail)
                for numero, ligne in enumerate(toutes_les_lignes, start=1):
                    lien = ligne[position_lien]
                    valeurs = vides
                    if lien:
                        time.sleep(delai)
                        try:
                            reponse = requests.get(lien, headers=HEADERS, timeout=15)
                            if reponse.status_code == 200:
                                valeurs = scraping.extraire_page(reponse.content, champs_detail, lien)
                        except requests.RequestException:
                            pass  # on garde des valeurs vides pour cette ligne
                    ligne.extend(valeurs)
                    # La page du navigateur reste en chargement : on suit l'avancement dans le terminal
                    print(f"Détail {numero}/{len(toutes_les_lignes)} : {lien}")
                colonnes += [nom for nom, _sel, _attr in champs_detail]
                logs.append({"level": "ok", "text": f"{len(toutes_les_lignes)} pages de détail lues"})

        # 6. Envoyer les résultats au template
        context["logs"] = logs
        context["columns"] = colonnes
        context["rows"] = toutes_les_lignes
        context["scrape"] = {"rows": len(toutes_les_lignes), "pages": pages_lues,
                             "duration": round(time.time() - debut, 1)}
        if pages_lues and not toutes_les_lignes:
            messages.warning(request, f"Aucun élément ne correspond au sélecteur « {form_data['container']} ».")

        # 7. Enregistrer la collecte dans un fichier CSV pour les étapes suivantes
        if toutes_les_lignes:
            chemin = stockage.enregistrer_csv(context["columns"], toutes_les_lignes)
            context["dataset_name"] = chemin.name
            context["download_url"] = reverse("telecharger", args=["collectes", chemin.name])
            messages.success(request, f"{len(toutes_les_lignes)} lignes enregistrées dans {chemin.name}.")

    return render(request, "data_analysis/webscrapping.html", context)


def telecharger(request, dossier, nom):
    """Envoie au navigateur un fichier produit par l'application, pour qu'il le télécharge."""
    chemin = stockage.chemin_fichier(dossier, nom)
    if chemin is None:
        raise Http404("Fichier introuvable")
    return FileResponse(open(chemin, "rb"), as_attachment=True, filename=chemin.name)


def cleaning(request):
    # La liste déroulante propose les fichiers produits par l'étape 1
    context = {"collectes": stockage.lister_collectes()}

    if request.method == "POST":
        source = request.POST.get("source", "")
        chemin = stockage.chemin_collecte(source)
        if chemin is None:
            messages.error(request, "Choisissez un fichier de collecte.")
            return render(request, "data_analysis/cleaning.html", context)

        # 1. Charger le CSV dans un DataFrame pandas
        df = pd.read_csv(chemin)

        # 2. Lire les choix du formulaire : une opération et un nouveau nom par colonne
        #    (au premier chargement, ils sont absents : "garder" et nom inchangé)
        choix = {col: request.POST.get(f"op_{col}", "garder") for col in df.columns}
        noms = {col: request.POST.get(f"nom_{col}", "").strip() for col in df.columns}
        noms = {col: nom for col, nom in noms.items() if nom and nom != col}

        # 3. Diagnostic : on regarde AVANT de modifier quoi que ce soit
        context.update({
            "source": source,
            "dataset_name": source,
            "before": nettoyage.resume(df),
            "column_profile": nettoyage.profil_colonnes(df),
            "columns": list(df.columns),
            "rows": nettoyage.apercu(df),
            # pour réafficher le formulaire colonne par colonne avec les choix de l'utilisateur
            "colonnes_form": [{"name": col, "op": choix[col], "rename": noms.get(col, "")} for col in df.columns],
            "doublons_coche": "doublons" in request.POST or request.POST.get("action") != "appliquer",
        })

        # 4. Nettoyer, seulement si l'utilisateur a cliqué sur « Appliquer »
        if request.POST.get("action") == "appliquer":
            if "doublons" in request.POST:
                df = df.drop_duplicates()
            df, journal = nettoyage.appliquer(df, choix, noms)

            if df.columns.duplicated().any():
                messages.error(request, f"Deux colonnes portent le même nom : {list(df.columns[df.columns.duplicated()])}.")
                return render(request, "data_analysis/cleaning.html", context)

            chemin_propre = stockage.enregistrer_nettoye(df, source)
            context.update({
                "after": nettoyage.resume(df),
                "column_profile": nettoyage.profil_colonnes(df),  # le profil APRÈS nettoyage
                "columns": list(df.columns),
                "rows": nettoyage.apercu(df),
                "journal": journal,
                "dataset_name": chemin_propre.name,
                "download_url": reverse("telecharger", args=["nettoyes", chemin_propre.name]),
            })
            messages.success(request, f"Jeu nettoyé enregistré dans {chemin_propre.name}.")

    return render(request, "data_analysis/cleaning.html", context)


def AED(request):
    # Formulaire en GET : l'analyse ne modifie rien, l'adresse /data/aed?source=… peut être partagée
    context = {"fichiers": stockage.lister("nettoyes")}
    source = request.GET.get("source", "")
    if source:
        chemin = stockage.chemin_fichier("nettoyes", source)
        if chemin is None:
            messages.error(request, "Fichier nettoyé introuvable.")
        else:
            df = pd.read_csv(chemin)
            context.update(exploration.analyser(df))
            context.update({"source": source, "dataset_name": source})
    return render(request, "data_analysis/aed.html", context)


def feeling_analysis(request):
    fichiers = stockage.lister("nettoyes")
    # Fichier choisi dans le formulaire, sinon le plus récent
    source = request.POST.get("source") or (fichiers[0] if fichiers else "")
    chemin = stockage.chemin_fichier("nettoyes", source) if source else None
    df = pd.read_csv(chemin) if chemin else None

    colonnes_texte = exploration.types_de_colonnes(df)[2] if df is not None else []
    defaut = "description" if "description" in colonnes_texte else (colonnes_texte[0] if colonnes_texte else "")
    form_data = {
        "text_column": request.POST.get("text_column", defaut),
        "text": request.POST.get("text", ""),
    }
    context = {"fichiers": fichiers, "source": source, "text_columns": colonnes_texte,
               "form_data": form_data, "onglet": "colonne"}

    if request.method == "POST":
        action = request.POST.get("action")
        resultats = None

        if action == "texte":
            # Texte libre : une ligne = un texte ; rien n'est enregistré
            context["onglet"] = "texte"
            textes = [ligne.strip() for ligne in form_data["text"].splitlines() if ligne.strip()]
            if not textes:
                messages.warning(request, "Saisissez au moins un texte.")
            else:
                resultats = sentiments.analyser_textes(textes)

        elif action == "colonne":
            colonne = form_data["text_column"]
            if df is None or colonne not in df.columns:
                messages.error(request, "Choisissez un fichier nettoyé et une colonne de texte qu'il contient.")
            else:
                df_enrichi, resultats = sentiments.enrichir(df, colonne)
                chemin_resultat = stockage.enregistrer_sentiments(df_enrichi, source)
                context["dataset_name"] = chemin_resultat.name
                context["download_url"] = reverse("telecharger", args=["sentiments", chemin_resultat.name])
                messages.success(request, f"Résultats enregistrés dans {chemin_resultat.name}.")

        if resultats:
            context["summary"] = sentiments.resume(resultats)
            # Textes analysés d'abord, du plus négatif au plus positif ; les non analysés à la fin
            context["results"] = sorted(resultats, key=lambda r: (r["score"] is None, r["score"] or 0))

    return render(request, "data_analysis/feeling.html", context)


def data_vizualization(request):
    # Les fichiers enrichis des sentiments d'abord (les plus complets), puis les fichiers nettoyés.
    # Valeur d'une option : "dossier:nom", par ex. "sentiments:sentiments_collecte_….csv"
    fichiers = [f"sentiments:{nom}" for nom in stockage.lister("sentiments")] + \
               [f"nettoyes:{nom}" for nom in stockage.lister("nettoyes")]
    # Formulaire en GET, comme l'AED : un graphique ne modifie rien, son adresse peut être partagée
    form_data = {cle: request.GET.get(cle, "") for cle in ("source", "chart_type", "x", "y", "color", "agg", "title")}
    form_data["source"] = form_data["source"] or (fichiers[0] if fichiers else "")
    form_data["chart_type"] = form_data["chart_type"] or "bar"
    form_data["agg"] = form_data["agg"] or "mean"
    context = {"fichiers": fichiers, "form_data": form_data}

    dossier, _, nom = form_data["source"].partition(":")
    chemin = stockage.chemin_fichier(dossier, nom) if nom else None
    if chemin is None:
        return render(request, "data_analysis/visualization.html", context)

    df = pd.read_csv(chemin)
    numeriques, categorielles, _texte = exploration.types_de_colonnes(df)
    context.update({
        "dataset_name": nom,
        "columns": categorielles + numeriques,  # axe X : catégories puis nombres
        "numeric_columns": numeriques,
        "categorical_columns": categorielles,
        "suggestions": visualisation.suggestions_pour(df),
    })

    # Un graphique n'est construit que si l'utilisateur a choisi un axe X
    if form_data["x"]:
        try:
            fig = visualisation.construire(df, form_data["chart_type"], form_data["x"], form_data["y"],
                                           form_data["color"], form_data["agg"], form_data["title"])
            context["chart_html"] = visualisation.en_html(fig)
        except ValueError as erreur:
            messages.error(request, str(erreur))

    return render(request, "data_analysis/visualization.html", context)
