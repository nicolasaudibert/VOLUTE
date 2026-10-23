# VOLUTE

*[English version](index.md)*

**V**ideo **O**bject **L**abeling, **U**ser-guided **T**racking and **E**xtraction

VOLUTE est une application de bureau qui segmente et suit des objets au fil d'une
séquence de trames vidéo. Désignez un objet sur une trame par une boîte et quelques
points : VOLUTE le suit dans toute la séquence, avec
[SAM 2](https://github.com/facebookresearch/segment-anything-2),
[MedSAM2](https://github.com/bowang-lab/MedSAM2) ou
[SAM2++](https://github.com/MCG-NJU/SAM2-Plus), et exporte masques, coordonnées,
centroïdes et contours. Tout fonctionne sur votre propre ordinateur.

Cette application a été développée pour la recherche en sciences de la parole, pour
suivre des structures articulatoires d'une trame à l'autre, mais aucune des méthodes
implémentées n'est spécifique à ce domaine. VOLUTE peut donc être appliqué à d'autres
domaines dans lesquels l'analyse de données vidéo est pertinente.

## Installation

Une seule commande installe VOLUTE et tout ce dont il a besoin, Python compris, dans
un dossier qui lui est propre. Les guides la détaillent sans supposer aucune
connaissance préalable de la ligne de commande :

- [Installer VOLUTE sous Windows](install-windows.fr.md)
- [Installer VOLUTE sous macOS](install-macos.fr.md)
- [Installer VOLUTE sous Linux (Ubuntu)](install-linux.fr.md)

Sous une autre distribution Linux, ou pour installer à la main, voir
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md) (en anglais).

## Utiliser VOLUTE

- Le [tutoriel](tutorial/index.fr.md) parcourt VOLUTE pas à pas, copies d'écran à
  l'appui, sur une courte vidéo d'IRM dynamique d'un locuteur.
- La section [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started)
  du README résume une première séance de travail en huit étapes (en anglais).
- La [FAQ](faq.fr.md) répond aux questions les plus courantes.
- La [documentation de référence](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md)
  décrit chaque fonction en détail (en anglais).

## Code source et aide

VOLUTE est un logiciel libre, distribué sous
[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). Son
code source est disponible sur [GitHub](https://github.com/nicolasaudibert/VOLUTE), où l'on
peut poser une question ou signaler un problème en ouvrant un ticket
([*issue*](https://github.com/nicolasaudibert/VOLUTE/issues)). Pour le citer, voir
[Comment citer VOLUTE ?](faq.fr.md#comment-citer-volute-)
