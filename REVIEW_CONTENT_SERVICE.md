# Review complete de `content_service/`

Date de revue : 2026-04-29  
Etat revu : implementation courante de `content_service/`, acces lecture Postgres content, recherche de similarite via Qdrant, lecture d'icones RSS et endpoints internes de consultation.

## Synthese executive

`content_service` est un service interne de lecture, plus simple que `admin_service`, mais il supporte tout de meme plusieurs responsabilites critiques : listing de sources, detail de source, similarite vectorielle Qdrant et lecture d'icones RSS.

Le service a de bons fondamentaux :

- Auth inter-services appliquee sur les routers agregateurs.
- Validation FastAPI correcte sur les parametres de pagination et d'identifiants.
- SQL parametre dans les clients DB revus.
- Protection du chemin de lecture des icones SVG contre les traversals les plus evidents.
- Decoupage clair entre routes, services, clients DB et integration Qdrant.

Verdict : le service est lisible et assez propre pour une facade interne de lecture, mais il reste sous-teste et manque surtout de garanties operationnelles. Le point le plus important est l'absence de readiness reelle, alors que certaines routes dependent fortement de Postgres et Qdrant.

## Ce qui est bien

- Les sous-routers sont attaches a des routers agregateurs qui imposent `require_internal_service_token`.
- `rss_icon_service.py` valide le chemin, force l'ancrage dans le repo RSS et limite les fichiers au `.svg`.
- Les endpoints de similarite encapsulent correctement les erreurs Qdrant en erreur upstream.
- Les routes gardent des limites de pagination raisonnables.
- Le code lecture reste principalement read-only et sans logique transactionnelle complexe.

## Findings prioritaires

### Eleve - Pas de readiness applicative reelle pour un service qui depend de Postgres et Qdrant

`content_service` n'expose que `GET /internal/health`, qui retourne un `ok` statique depuis `content_service/main.py`.

Impact : un orchestrateur peut considerer le service sain alors que :

- Postgres content est indisponible ;
- Qdrant est indisponible ;
- la configuration Qdrant est invalide ;
- les requetes de similarite echoueront immediatement au runtime.

Recommandation :

- Ajouter un endpoint de readiness equivalent a ce que `admin_service` expose deja.
- Verifier au minimum Postgres et Qdrant.
- Conserver `/internal/health` comme simple liveness et separer clairement readiness/liveness.

### Eleve - Le service initialise une connexion identity DB qu'il n'utilise pas

`content_service/database.py` resolve, cree et maintient un engine `IDENTITY_DATABASE_URL`, alors que les routes lues pendant cette revue n'utilisent que `get_content_db_session()`.

Impact :

- dependance de configuration inutile ;
- consommation de connexions/pool inutile ;
- risque de blocage au demarrage si `IDENTITY_DATABASE_URL` est exige en environnement strict alors qu'aucun endpoint n'en depend.

Recommandation :

- Supprimer l'engine identity du service si elle n'est pas necessaire.
- Si une extension future en a besoin, charger cette dependance de facon explicite et paresseuse.
- Ajouter un test de demarrage avec configuration minimale strictement requise.

### Eleve - Couverture de tests quasi nulle

Comme pour `admin_service`, le seul test present est `content_service/tests/test_source_syntax.py`.

Impact : aucun filet automatique ne couvre :

- auth inter-service ;
- routing effectif des routers agregateurs ;
- `rss_icon_service` et ses cas limites ;
- erreurs `SourceNotFoundError` ;
- integration Qdrant ;
- SQL de pagination et de filtrage.

Recommandation :

- Ajouter des tests unitaires sur `shared_backend/security/internal_service_auth.py`, `app/rss/services/rss_icon_service.py` et `app/analytics/services/analysis_service.py`.
- Ajouter des tests d'integration HTTP sur les principales routes `/internal/content/*`.
- Ajouter au moins une suite DB pour les lectures paginees et les details de source.

### Moyen/Eleve - `APP_ENV` peut bypasser l'auth inter-service malgre une intention stricte

La meme logique que dans `admin_service` existe maintenant dans `shared_backend/security/internal_service_auth.py`.

Impact : un environnement non local mal configure avec `APP_ENV=dev` ou equivalent pourrait accepter des appels internes sans token.

Recommandation :

- Faire primer `REQUIRE_INTERNAL_SERVICE_TOKEN=true` sur `APP_ENV`.
- Ajouter des tests sur la matrice de configuration.

### Moyen - Contrats et schemas locaux dupliques

`content_service` embarque ses propres schemas internes et de lecture au lieu de partager un package commun versionne avec les autres services.

Impact : risque de drift entre `public_api`, `content_service` et d'autres consommateurs pour :

- schemas analytics ;
- schemas sources ;
- schemas internal service health.

Recommandation :

- Mutualiser les schemas vraiment partages.
- Ajouter des tests de contrat ou snapshots de payloads.

### Moyen - `SimpleQdrantClient` synchrone, sans mutualisation de connexion ni observabilite

Le client Qdrant cree un `httpx.Client` par appel lorsqu'aucun client n'est injecte.

Impact : cout reseau et absence de metrics sur une fonctionnalite potentiellement sensible en latence.

Recommandation :

- Evaluer un client mutualise ou injecte au niveau service.
- Ajouter logs/metrics sur latence, erreurs et volume des requetes de similarite.

### Moyen - Image Docker et runtime encore peu durcis

Le `Dockerfile` reste tres basique : image Python slim, installation de `git`, execution implicite en root.

Impact : surface d'image inutilement large pour un service de lecture qui n'a pas besoin de Git pour servir ses routes principales.

Recommandation :

- Passer a un utilisateur non-root.
- Retirer `git` si le service n'en a pas besoin au runtime.
- Evaluer un build multi-stage.

## Securite detaillee

### Inter-service

Bon :

- Header dedie `x-manifeed-internal-token`.
- Comparaison constant-time.
- Protection appliquee sur les routers agregateurs `/internal/content/*`.

Reste a faire :

- Corriger la priorite `APP_ENV` vs `REQUIRE_INTERNAL_SERVICE_TOKEN`.
- Ajouter des tests de non-regression.

### Lecture d'icones

Bon :

- Rejet des chemins absolus.
- Rejet des `..`.
- Verification que le fichier final reste sous le repository RSS.
- Limitation aux fichiers `.svg`.

Reste a faire :

- Ajouter des tests unitaires sur les cas d'entree invalides et sur les chemins valides.

## Architecture

L'architecture est simple et adaptee a un service read-only :

- `app/sources/router` pour l'exposition HTTP ;
- `app/sources/services` pour les cas d'usage de lecture ;
- `app/sources/database` pour les requetes SQL ;
- `app/analytics/services` pour l'integration Qdrant ;
- `app/rss/services` pour la lecture d'icones.

Le principal point d'attention n'est pas le design du code mais l'ecart entre la simplicite apparente du service et ses dependances reelles, surtout Qdrant.

## Contrats API actuels

Routes principales observees :

- `GET /internal/health` : liveness statique.
- `GET /internal/content/admin/sources/*` : lectures RSS admin.
- `GET /internal/content/sources/*` : lectures user.
- `GET /internal/content/analysis/overview` : overview content + collection Qdrant.
- `GET /internal/content/analysis/similar-sources` : similarite par source.
- `GET /internal/content/rss/img/{icon_url}` : lecture d'icone SVG.

## Tests et verification

Verifications executees pendant cette revue :

- `python3 -m compileall -q content_service` : OK.
- Lecture des routers, services de lecture, client Qdrant, securite inter-service et gestion des icones RSS.

Limites de verification :

- `pytest` n'est pas installe dans l'environnement courant.
- Les dependances de runtime comme `fastapi` ne sont pas installees ici, donc un import complet de l'application n'a pas pu etre verifie.
- Pas de test d'integration Postgres ni Qdrant pendant cette revue.

## Plan d'action recommande

### P0 - Avant trafic reel plus important

- Ajouter un vrai endpoint de readiness pour Postgres et Qdrant.
- Retirer la dependance identity DB si elle est inutile.
- Ajouter des tests comportementaux sur auth, routing, icones RSS et similarite.
- Faire primer `REQUIRE_INTERNAL_SERVICE_TOKEN=true` sur `APP_ENV`.

### P1 - Stabilisation

- Ajouter observabilite sur Qdrant et sur les endpoints de lecture critiques.
- Mutualiser les schemas partages ou ajouter des tests de contrat.
- Durcir l'image Docker.

### P2 - Long terme

- Evaluer un client Qdrant plus mutualise si le trafic monte.
- Renforcer les tests SQL de pagination, filtres et details de source.
