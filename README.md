# App Data — pipeline d'analyse de données web

Application Django qui enchaîne les cinq étapes d'une analyse de données, de la page web au graphique :

| Étape | Page | Ce qu'elle fait | Bibliothèques |
|---|---|---|---|
| 1. Collecte | `/data/webscrapping` | Extrait des données d'un site à partir de sélecteurs CSS saisis dans un formulaire, avec pagination et pages de détail | requests, BeautifulSoup |
| 2. Nettoyage | `/data/cleaning` | Choisit une opération par colonne (nombre, note, texte, catégorie, genre…) et compare avant / après | pandas |
| 3. Analyse exploratoire | `/data/aed` | Statistiques descriptives, valeurs manquantes, distributions, corrélations, observations automatiques | pandas, Plotly |
| 4. Analyse de sentiments | `/data/feeling` | Score de −1 à +1 par texte, avec les mots qui l'expliquent ; détection de la langue | VADER, langdetect |
| 5. Visualisation | `/data/visualization` | Constructeur de graphiques piloté par formulaire, suggestions, export PNG | Plotly |

Chaque étape lit le fichier CSV produit par la précédente (`media/collectes/` → `media/nettoyes/` → `media/sentiments/`).
Le site d'entraînement utilisé pendant le développement est [books.toscrape.com](https://books.toscrape.com/), conçu pour s'exercer au web scraping.

## Installation

Prérequis : Python 3.11 et PostgreSQL.

```bash
git clone <adresse-du-depot>
cd <dossier-du-depot>

python -m venv venv
venv\Scripts\activate            # Windows  (Linux / macOS : source venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env           # Windows  (Linux / macOS : cp .env.example .env)
```

Ouvrez ensuite `.env` et renseignez :
- `DJANGO_SECRET_KEY` : générez-en une avec
  `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`
- `DB_PASSWORD` (et les autres `DB_*` si besoin) : l'accès à votre base PostgreSQL.

Créez la base `db_data` dans PostgreSQL, puis :

```bash
python manage.py migrate
python manage.py runserver
```

L'application est disponible sur http://127.0.0.1:8000/data/.

## Organisation du code

```
App_data/              configuration du projet (settings.py lit les secrets dans .env)
data_analysis/
├── views.py           une vue par page : lit le formulaire, appelle les modules, prépare l'affichage
├── scraping.py        collecte : lecture des sélecteurs, extraction, page suivante
├── nettoyage.py       nettoyage : opérations par colonne, regroupement en genres
├── exploration.py     analyse exploratoire : statistiques, graphiques, observations
├── sentiments.py      analyse de sentiments : VADER, langue, mots déterminants
├── visualisation.py   construction des graphiques Plotly
├── stockage.py        enregistrement et lecture sécurisée des fichiers CSV
├── templates/         pages HTML (base.html + une page par étape + composants)
└── static/            feuille de style et script
```

Les modules de traitement (`scraping`, `nettoyage`, `exploration`, `sentiments`, `visualisation`) ne dépendent pas de Django et peuvent être testés séparément.

## Bon usage du web scraping

Respectez le fichier `robots.txt` et les conditions d'utilisation des sites visés, et gardez un délai entre les requêtes (champ « Délai » du formulaire). Certains sites, comme Amazon, interdisent la collecte automatisée et bloquent les robots.

## Limites connues

- L'analyse de sentiments (VADER) ne traite que l'anglais ; les autres langues sont détectées et mises de côté.
- Sur des descriptions de produits, le score mesure le ton du vocabulaire, pas l'avis des clients.
- La collecte s'exécute pendant la requête : la page reste en chargement pendant les longues collectes.
