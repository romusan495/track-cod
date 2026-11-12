# Mettre le site Track COD en ligne (Cloudflare, gratuit)

Le site (classement + pages joueurs) tourne sur le compte Cloudflare **Workers Free** du propriétaire. Toutes les commandes se lancent dans un terminal, depuis le dossier `worker` du projet. Il faut Node.js ≥ 20 (`node --version`).

## Première mise en ligne

1. **Connexion à Cloudflare.** C'est toi qui te connectes, dans ton navigateur.

   ```bash
   npx wrangler login
   ```

2. **Créer la base de données.**

   ```bash
   npx wrangler d1 create track-cod
   ```

   Copie le `database_id` affiché dans `worker/wrangler.toml`, à la place de `00000000-0000-0000-0000-000000000000`.

3. **Créer la table des joueurs.**

   ```bash
   npx wrangler d1 execute track-cod --remote --file=schema.sql
   ```

4. **Clé admin (modération).** Tape une longue chaîne au hasard quand on te la demande, et garde-la dans un endroit sûr (gestionnaire de mots de passe). Elle n'est jamais écrite dans le projet.

   ```bash
   npx wrangler secret put ADMIN_KEY
   ```

5. **Publier le site.**

   ```bash
   npx wrangler deploy
   ```

   L'adresse s'affiche, du type `https://track-cod.<ton-sous-domaine>.workers.dev`.

6. **Brancher le traqueur.** Mets cette adresse dans `trackcod/publish.py` (`SITE_URL`), puis reconstruis l'installeur.

## Mettre à jour le site

Après une modification de `site/` ou `worker/src/` :

```bash
npm test
```

```bash
npx wrangler deploy
```

## Modération : retirer un profil

L'identifiant du joueur est dans l'adresse de sa page (`joueur.html?id=…`).

```bash
curl -X DELETE -H "Authorization: Bearer TA_CLE_ADMIN" https://track-cod.<ton-sous-domaine>.workers.dev/api/players/IDENTIFIANT
```

Le traqueur de ce joueur arrête alors de publier et lui affiche « ton profil a été retiré du site ».

## Ce qui est automatique

- Un profil sans mise à jour depuis 90 jours est supprimé chaque nuit (tâche planifiée à 4 h UTC).
- Les valeurs absurdes sont refusées par le serveur.
