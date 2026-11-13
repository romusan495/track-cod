# Signature du programme et Microsoft Store

But : que Windows n'affiche plus « Windows a protégé votre ordinateur » (SmartScreen) à l'installation, et
pouvoir publier Track COD sur le Microsoft Store. Recherche faite le 13/11/2026 ; vérifie les conditions au moment
de t'inscrire, elles changent.

## Pourquoi l'avertissement

L'installateur n'est pas signé. SmartScreen se méfie des programmes non signés et peu téléchargés, et chaque
nouvelle version repart de zéro. Une signature fait remonter la réputation à l'éditeur, plus au fichier.

## Les options, de la plus adaptée à la moins adaptée

### 1. SignPath Foundation (gratuit, pour les projets open source) — recommandé

Conditions principales ([conditions officielles](https://signpath.org/terms)) :

- **Une licence open source approuvée OSI** sur tout le projet, sans double licence commerciale.
  **Le dépôt n'a aucune licence aujourd'hui** : c'est à toi de la choisir. Les deux choix courants :
  - **MIT** : tout le monde peut réutiliser le code, même dans un projet fermé, en gardant ton nom.
  - **GPL-3.0** : qui réutilise le code doit publier le sien sous la même licence.
- Pas de logiciel malveillant ni « potentiellement indésirable ».
- Le code est public (c'est déjà le cas) et, d'après des guides non officiels, l'installateur doit être **construit
  automatiquement sur GitHub** (GitHub Actions) depuis le dépôt public, pour que SignPath vérifie que le fichier
  signé correspond bien au code. Aujourd'hui l'installateur est construit sur ton PC : il faudrait ajouter ce
  build automatique.
- L'éditeur affiché par Windows est **« SignPath Foundation »**, pas « Romusan ».
- Il faut une page « politique de signature » et citer SignPath dans la documentation (beaucoup de projets le
  font, par exemple [Pandoc](https://pandoc.org/code-signing-policy.html)).

Démarche : choisir la licence → ajouter le build GitHub Actions → faire une release construite par GitHub →
postuler sur [signpath.org](https://signpath.org/) → brancher la signature dans le build.

### 2. Azure Artifact Signing (ex-Trusted Signing) — pas possible pour toi

Environ 10 $/mois, mais réservé aux **particuliers des États-Unis et du Canada** (les entreprises : aussi UE et
Royaume-Uni). ([retour d'expérience](https://www.itwriting.com/blog/?p=12462),
[tarifs Microsoft](https://azure.microsoft.com/fr-fr/pricing/details/artifact-signing/))

### 3. Certificat classique (OV) — à éviter

Plusieurs centaines d'euros par an, avec une clé matérielle obligatoire. Contraire au « 100 % gratuit ».

## Microsoft Store

- **L'inscription est gratuite pour les particuliers** depuis 2025, avec un compte Microsoft personnel, sur
  [storedeveloper.microsoft.com](https://storedeveloper.microsoft.com)
  ([annonce](https://alternativeto.net/news/2025/9/microsoft-finally-drops-microsoft-store-publishing-fee-for-individual-developers-globally)).
- **Installateur .exe** : le Store ne le signe pas à ta place. Il doit **déjà être signé** par un certificat
  reconnu, et rester à une adresse fixe sans changer
  ([FAQ Microsoft](https://learn.microsoft.com/fr-fr/windows/apps/publish/faq/get-started-with-the-microsoft-store)).
  Donc : **d'abord SignPath (option 1), ensuite le Store.**
- Autre voie, plus lourde : un paquet **MSIX**, que le Store signe lui-même. Mais il faudrait
  revoir l'installation et couper la mise à jour automatique (le Store s'en charge), et tester la capture d'écran
  dans ce format. À garder en réserve.
- Un outil qui lit l'écran d'un jeu peut être refusé à la certification ; la page Transparence et l'interrupteur
  à distance aident à le défendre.

## Ce qui t'attend, dans l'ordre

1. **Choisir la licence** (MIT ou GPL-3.0) — décision à toi.
2. Je prépare le build automatique sur GitHub et la page « politique de signature ».
3. Tu postules à SignPath Foundation (formulaire à ton nom, je ne peux pas le remplir à ta place).
4. Une fois signé : tu crées ton compte développeur Microsoft Store, et on soumet l'installateur.
