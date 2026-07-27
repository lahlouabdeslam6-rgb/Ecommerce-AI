# Production NUTRIFIT

Cette configuration prepare l'application complete derriere un reverse proxy
Nginx. MongoDB, Redis, Qdrant, Ollama, le backend, le frontend et n8n restent
sur le reseau Docker prive. Seul le port HTTP du gateway est expose.

## Prerequis

- un serveur Linux avec Docker Engine et Docker Compose ;
- un nom de domaine pointe vers le serveur ;
- TLS gere par le fournisseur, un load balancer ou un reverse proxy externe ;
- des volumes Docker sauvegardes regulierement ;
- les identifiants SMTP et WhatsApp Cloud pour activer les envois externes.

## Variables obligatoires

Copier `.env.example` vers `.env`, puis remplacer toutes les valeurs de
demonstration. Les secrets les plus importants sont :

- `MONGO_ROOT_PASSWORD`
- `JWT_SECRET_KEY`
- `AUTOMATION_API_KEY`
- `N8N_ENCRYPTION_KEY`
- `PUBLIC_APP_URL`
- `N8N_PUBLIC_HOST`
- `N8N_WEBHOOK_URL`

Valider avant le premier demarrage :

```powershell
powershell -ExecutionPolicy Bypass -File scripts/production-check.ps1
```

## Demarrage

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Lancer ensuite le smoke test sur l'URL publique :

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 `
  -FrontendUrl "https://votre-domaine.ma" `
  -BackendUrl "https://votre-domaine.ma"
```

## n8n

Trois workflows sont importes :

1. analyse horaire des retards de livraison ;
2. relance des paniers abandonnes apres 24 heures ;
3. routage de l'outbox vers email ou WhatsApp.

Les deux premiers peuvent etre actives apres verification de
`AUTOMATION_API_KEY`. Le troisieme reste volontairement inactif jusqu'a la
configuration des credentials SMTP et WhatsApp Cloud. Un message externe n'est
jamais marque comme envoye tant que le connecteur reel ne l'a pas confirme.

Pour finaliser les envois externes dans l'interface n8n :

1. creer le premier compte proprietaire sur l'URL n8n ;
2. ouvrir `NUTRIFIT - Email and WhatsApp outbox` ;
3. remplacer `Configurer SMTP puis activer` par un noeud d'envoi email avec
   les champs `recipient`, `subject` et `body` de l'outbox ;
4. remplacer `Configurer WhatsApp Cloud puis activer` par le connecteur
   WhatsApp Cloud du fournisseur ;
5. apres chaque envoi confirme, appeler
   `POST /api/automations/outbox/{id}/complete` avec `{"success": true}` et la
   meme cle `X-Automation-Key` ;
6. tester les deux branches, puis activer le workflow.

Sans ces credentials externes, les notifications internes du site fonctionnent
normalement et les messages email/WhatsApp restent conserves dans l'outbox.

## Limite SQLite

SQLite convient au MVP et a un deploiement mono-instance. Pour plusieurs
instances backend ou un fort volume de commandes, migrer les donnees
transactionnelles vers PostgreSQL avant la mise a l'echelle.
