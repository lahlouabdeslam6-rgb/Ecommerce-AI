# NUTRIFIT Ecommerce AI

Plateforme e-commerce de nutrition sportive construite avec FastAPI, MongoDB,
SQLite, Redis, Qdrant, Ollama, React/Vinext et Docker.

## Etat actuel

Le MVP local et l'infrastructure IA sont fonctionnels :

- catalogue, recherche, filtres et tri ;
- panier et commandes avec paiement a la livraison ;
- espaces client, support et administration ;
- gestion des produits, du stock et des photos ;
- tickets support et notifications ;
- authentification JWT avec refresh token ;
- verification email et reinitialisation du mot de passe en mode local ;
- audit logs, historique du stock et monitoring ;
- migrations Alembic et sauvegardes MongoDB/SQLite.
- cache et memoire courte duree avec Redis ;
- base vectorielle Qdrant pour la recherche semantique ;
- Ollama local avec un modele de generation et un modele d'embeddings ;
- health check et self-test admin de toute l'infrastructure IA.
- Product Agent avec proposition controlee de description, categorie, SEO et
  tags, validation admin obligatoire et indexation Qdrant.
- Content Agent avec generation de brouillons, edition admin, publication,
  archivage et affichage controle sur la homepage.
- Marketing Agent avec campagnes multi-canaux, edition, validation admin et
  archivage, sans envoi automatique ni modification des prix.
- Safety Agent avec controle par regles et Ollama, historique admin et blocage
  des promesses medicales avant application ou publication d'un contenu AI.
- Recommendation Agent avec suggestions similaires sur les fiches produits,
  personnalisation par panier, commandes, objectif et budget, Qdrant avec
  fallback MongoDB, uniquement sur les produits actifs et disponibles.
- Analytics Agent avec indicateurs sur 7, 30 ou 90 jours, comparaison avec la
  periode precedente, produits les plus vendus, produits sans vente et resume
  Ollama optionnel en lecture seule.
- Stock Forecast Agent avec vitesse de vente, jours de couverture, date de
  rupture estimee, priorites et quantites de reapprovisionnement suggerees,
  sans modification automatique du catalogue.
- AI Orchestrator avec detection d'intention en francais, anglais et darija
  latine, coordination Product, Recommendation, Content, Marketing, Analytics
  et Safety, assistant client et espace de supervision admin avec historique.

Le paiement reel, l'envoi d'emails reel et les agents Support et Delivery sont
prevus dans les prochaines phases.

## Demarrage local

1. Copier `.env.example` vers `.env`.
2. Remplacer les valeurs de demonstration par des secrets locaux.
3. Demarrer les services :

```powershell
docker compose up -d --build
```

Au premier demarrage uniquement, installer les modeles Ollama :

```powershell
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull nomic-embed-text
```

## URLs

- Site : http://localhost:5173
- API : http://localhost:8000
- Documentation API : http://localhost:8000/docs
- Health check : http://localhost:8000/health
- MongoDB depuis Windows : `localhost:27018`
- Redis depuis Windows : `localhost:6379`
- Qdrant dashboard : http://localhost:6333/dashboard
- Ollama depuis Windows : http://localhost:11435

Les routes admin `GET /api/admin/ai/status` et `POST /api/admin/ai/test`
permettent de verifier les services, les modeles, le cache, les embeddings,
la collection vectorielle et la generation locale.

Le Product Agent est disponible dans la fiche de modification d'un produit.
Il ne modifie jamais le catalogue automatiquement : l'admin genere, relit,
peut corriger puis valide la proposition.

Le Content Agent est disponible dans `Administration > Contenu AI`. Les
contenus restent en brouillon jusqu'a leur publication manuelle. Les types
`homepage_hero` et `promotion` publies peuvent alimenter la page d'accueil.

Le Marketing Agent est disponible dans `Administration > Marketing AI`. Il
prepare des brouillons Instagram, Facebook, email et WhatsApp. Une validation
admin marque la campagne comme prete, sans l'envoyer automatiquement.

Le Safety Agent est disponible dans `Administration > Safety AI`. Il controle
automatiquement Product Agent, Content Agent et Marketing Agent au moment de
la validation. Un contenu conforme passe, un doute est trace pour review et
une promesse medicale dangereuse bloque l'action avant toute modification.

Le Recommendation Agent apparait sous les fiches produits et dans le panier.
Il classe les produits disponibles avec Qdrant et les donnees du catalogue. Le
client connecte peut aussi choisir un objectif et un budget maximum par produit.

L'Analytics Agent est disponible dans `Administration > Analytics AI`. La
route admin `GET /api/admin/ai/analytics/report` calcule les ventes et tendances
sur 7, 30 ou 90 jours. Le bouton de resume IA utilise Ollama et conserve un
resume local de secours si le modele est indisponible. Cette analyse est
strictement en lecture seule.

Le Stock Forecast Agent est disponible dans `Administration > Stock
intelligent`. La route admin `GET /api/admin/ai/stock-forecast/report` calcule
les risques de rupture a partir du stock MongoDB et des ventes SQLite. Ollama
peut rediger une analyse, mais aucune quantite n'est appliquee automatiquement.

L'AI Orchestrator est disponible avec `POST /api/orchestrator/execute`. Le
client connecte utilise l'assistant flottant pour chercher des produits selon
son objectif et son budget. L'admin dispose de `Administration > AI
Orchestrator` pour tester le routing, consulter les resultats des agents et la
decision Safety. `GET /api/orchestrator/history` est reserve a l'admin et
retourne l'historique trace dans les audit logs. Les actions de modification,
publication et envoi restent en mode proposition : aucune action metier n'est
executee automatiquement.

## Tests

```powershell
docker compose run --rm --no-deps backend pytest -q
docker compose run --rm --no-deps frontend npm test
```

Le workflow QA complet est disponible dans
`backend/tests/manual_full_qa.py`. Il utilise uniquement des donnees
temporaires et les nettoie apres execution.

## Sauvegarde

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/backup.ps1
```

Les fichiers `.env`, bases locales, images uploadees, dependances et sauvegardes
ne sont jamais versions dans Git.
