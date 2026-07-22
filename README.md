# NUTRIFIT Ecommerce AI

Plateforme e-commerce de nutrition sportive construite avec FastAPI, MongoDB,
SQLite, React/Vinext et Docker.

## Etat actuel

Le MVP local sans agents IA est fonctionnel :

- catalogue, recherche, filtres et tri ;
- panier et commandes avec paiement a la livraison ;
- espaces client, support et administration ;
- gestion des produits, du stock et des photos ;
- tickets support et notifications ;
- authentification JWT avec refresh token ;
- verification email et reinitialisation du mot de passe en mode local ;
- audit logs, historique du stock et monitoring ;
- migrations Alembic et sauvegardes MongoDB/SQLite.

Le paiement reel, l'envoi d'emails reel et les agents IA sont prevus dans les
prochaines phases.

## Demarrage local

1. Copier `.env.example` vers `.env`.
2. Remplacer les valeurs de demonstration par des secrets locaux.
3. Demarrer les services :

```powershell
docker compose up -d --build
```

## URLs

- Site : http://localhost:5173
- API : http://localhost:8000
- Documentation API : http://localhost:8000/docs
- Health check : http://localhost:8000/health
- MongoDB depuis Windows : `localhost:27018`

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
