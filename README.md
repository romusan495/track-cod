# Track COD

Une fenêtre pour ton 2ᵉ écran qui suit tes **camos MW4** et tes **stats multijoueur**, pendant que tu joues :

- l'**arme jouée**, lue sur l'écran de choix de classe ;
- le **camo à faire maintenant** (défi et compteur), puis l'état des militaires, des spéciaux et de l'Érudit ;
- la **classe méta** de l'arme, d'après [L'antre de Romusan · MW4](https://romusan495.github.io/antre-de-romusan/mw4/) ;
- ta **dernière partie** et tes **stats globales**, mises à jour à chaque fin de match.

Track COD **lit seulement l'écran** (capture + reconnaissance de texte de Windows). Il ne touche jamais au jeu.

> Track COD n'est pas affilié à Activision ni à Call of Duty.

## Pour les joueurs

### Installer
1. Va dans [Releases](https://github.com/romusan495/track-cod/releases/latest) et télécharge `TrackCOD-Setup-x.y.z.exe`.
2. Lance-le et suis l'assistant. Pas besoin de droits administrateur : Track COD s'installe dans ton dossier utilisateur, avec un raccourci dans le menu Démarrer (et sur le Bureau si tu veux).
3. Pour le désinstaller : Paramètres > Applications > Track COD.

Au premier lancement, Windows peut afficher « Windows a protégé votre ordinateur », parce que l'app n'est pas signée. Clique sur **Informations complémentaires**, puis sur **Exécuter quand même**.

### Prérequis
- Windows 10 ou 11 **en français**. La reconnaissance de texte française est alors déjà installée. Si elle manque, l'app te dit comment l'ajouter.
- Jeu en **fenêtré sans bordure**, client du jeu en français.

### Mises à jour
À l'ouverture, Track COD vérifie s'il existe une nouvelle version et te propose de l'installer. La mise à jour se fait toute seule (Track COD se ferme puis se relance). Tes fiches et tes stats sont gardées, même après une désinstallation.

### Ce que tu dois faire dans le jeu

| Pour… | Fais… |
|---|---|
| apprendre une arme (camos, compteurs) | ouvre **Apparence** et reste ~2 s sur chaque camo qui t'intéresse |
| l'arme jouée | rien : elle est lue sur **Choisir la classe** en début de partie (ou clique sur son nom dans la fenêtre) |
| la dernière partie | rien : le **tableau des scores** de fin de match est lu tout seul |
| calibrer le global | ouvre une fois **Carrière > Rapport de combat** (vue Multijoueur) ; ensuite chaque partie s'ajoute toute seule |

**Ce qui s'affiche :**
- **?** : pas encore lu ;
- **▶** : disponible ;
- **🔒** : verrouillé (la condition est affichée) ;
- **✔** : fait.

Un nom suivi de « ? » n'a été lu qu'une fois ; il se fixe dès la lecture suivante.

### Tes données
Elles sont dans `%LOCALAPPDATA%\TrackCOD\` : fiches et stats (`state.json`), parties lues (`matches.jsonl`), classes méta en cache (`meta-cache.json`).

### Le site des stats
Le classement des joueurs et une page par joueur sont sur **https://track-cod.romusangames.workers.dev**, lisibles sur téléphone.

Pour y apparaître :
1. Dans la fenêtre du traqueur, section « SITE », choisis un pseudo.
2. Coche « Publier mes stats sur le site ». La case « Montrer ma maîtrise des camos » est facultative.

Rien n'est publié sans cette case, et seuls tes propres chiffres sont envoyés. Décoche-la, ou clique sur « Me retirer du site », pour tout effacer.

## Développement

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\pytest
.venv\Scripts\python -m trackcod --demo
```

- `python -m trackcod --check` : diagnostic de la machine, écrit dans `%LOCALAPPDATA%\TrackCOD\check.txt`.
- `python -m tools.collect` (ou `lancer-collecte.bat`) : enregistre des captures pendant que tu joues, avec une rafale de 10 s après chaque changement. Sert à régler la lecture d'un nouvel écran.
- Site des stats (dossiers `site/` et `worker/`, Cloudflare Workers + D1) : tests avec `cd worker && npm test`, mise en ligne décrite dans [docs/site-deploiement.md](docs/site-deploiement.md).
- `python -m tools.build` : construit `dist\TrackCOD\TrackCOD.exe`, puis l'installateur `dist\TrackCOD-Setup-<version>.exe`. Il faut Inno Setup : `winget install JRSoftware.InnoSetup`.

**Publier une version :**
1. Monter `__version__` dans `trackcod/__init__.py`.
2. Lancer `python -m tools.build`.
3. Lancer `gh release create v<version> dist\TrackCOD-Setup-<version>.exe`.
