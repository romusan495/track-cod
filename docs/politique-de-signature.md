# Politique de signature du code / Code signing policy

*Version française ci-dessous.*

## English

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by
[SignPath Foundation](https://signpath.org). *(Applies once the project is accepted by SignPath Foundation.)*

**What is signed:** only the Windows installer `TrackCOD-Setup-<version>.exe` and the program it contains, built by
the [GitHub Actions workflow](../.github/workflows/build.yml) of this repository from the tagged public source. No
binary built on a personal computer is ever signed.

**Team roles**

| Role | Members |
|------|---------|
| Committers and reviewers | [romusan495](https://github.com/romusan495) (Romusan) |
| Approvers | [romusan495](https://github.com/romusan495) (Romusan) |

Every release is approved by hand before it is signed.

**Privacy policy:** this program will not transfer any information to other networked systems unless specifically
requested by the user or the person installing or operating it, with these exceptions, all described on the
[transparency page](https://track-cod.romusangames.workers.dev/transparence.html):

- update check: it reads the latest release on GitHub;
- weapon meta builds: it reads public pages, without sending anything about the user;
- remote switch: it reads `etat.json` on the Track COD website, which can suspend screen reading;
- stats website: the user's own stats are sent **only if the user ticks « Publier mes stats »**; full details in the
  [privacy notice](https://track-cod.romusangames.workers.dev/confidentialite.html).

Track COD never reads or modifies game memory, never injects code, never sends input to the game, and never sends
other players' names or any game image.

## Français

Signature de code gratuite fournie par [SignPath.io](https://about.signpath.io), certificat de la
[SignPath Foundation](https://signpath.org). *(S'applique une fois le projet accepté par la SignPath Foundation.)*

**Ce qui est signé :** uniquement l'installateur Windows `TrackCOD-Setup-<version>.exe` et le programme qu'il
contient, construits par le [build GitHub Actions](../.github/workflows/build.yml) de ce dépôt à partir du code
public de la version. Aucun fichier construit sur un PC personnel n'est signé.

**Rôles :** Romusan ([romusan495](https://github.com/romusan495)) écrit, relit et approuve chaque version à la
main avant sa signature.

**Vie privée :** le programme n'envoie aucune information sur le réseau sans que l'utilisateur l'ait demandé, sauf
ce qui est décrit sur la [page Transparence](https://track-cod.romusangames.workers.dev/transparence.html) : vérifier
les mises à jour (GitHub), lire les classes méta (pages publiques), lire l'interrupteur à distance du site. Les stats
ne sont envoyées sur le site **que si tu coches « Publier mes stats »** (détails dans la
[politique de confidentialité](https://track-cod.romusangames.workers.dev/confidentialite.html)).
