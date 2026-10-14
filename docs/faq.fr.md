# Questions fréquentes

*[English version](faq.md)*

Des réponses courtes, renvoyant chacune à l'emplacement où le sujet est traité en détail :
le [tutoriel](tutorial/index.fr.md) de ce site, qui montre les fonctions pas à pas sur un
exemple, ou la documentation de référence, en anglais, c'est-à-dire les fichiers
`INSTALL.md`, `README.md` et `DOCUMENTATION.md` du dépôt GitHub. Chaque lien précise vers
lequel des deux il mène. Les menus sont cités tels qu'ils apparaissent dans VOLUTE en
français.

- [Installation et démarrage](#installation-et-démarrage)
- [Utilisation de VOLUTE](#utilisation-de-volute)
- [Données, résultats et citation](#données-résultats-et-citation)

## Installation et démarrage

### Faut-il connaître Python, ou l'installer d'abord ?

Non. Sous Windows et macOS, une seule commande installe tout ce dont VOLUTE a besoin,
Python compris ; les guides [Windows](install-windows.fr.md) et [macOS](install-macos.fr.md)
la détaillent sans supposer aucune connaissance de la ligne de commande.

### L'installation modifie-t-elle mon Python, Anaconda ou Miniconda existant ?

Non. VOLUTE est installé dans son propre dossier, avec sa propre copie de Python, et rien
n'est modifié en dehors de ce dossier, hormis le raccourci de VOLUTE. Désinstaller revient
à supprimer ce dossier et le raccourci.

### Peut-on installer VOLUTE sous Linux ?

Oui, à la main : la documentation de référence, sur GitHub, décrit chaque étape dans
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md).
L'installation en une seule commande ne couvre pour l'instant que Windows et macOS.

### VOLUTE a-t-il besoin d'une connexion à Internet ?

Seulement pour être installé ou mis à jour. Une fois installé, il fonctionne hors ligne :
voir aussi
[Mes données sont-elles envoyées quelque part ?](#mes-données-sont-elles-envoyées-quelque-part-)

### Comment mettre VOLUTE à jour ?

Relancez la commande d'installation : VOLUTE est mis à jour vers sa dernière version, vos
réglages sont conservés, et rien de ce qui est déjà installé n'est téléchargé à nouveau.
La même commande ajoute des modèles, et reprend une installation interrompue. Pour une
installation faite à la main, voir la documentation de référence, sur GitHub :
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#gui-installation).

### Ma carte graphique est-elle utilisée ?

VOLUTE choisit de lui-même le dispositif le plus rapide disponible : par ordre de
préférence une carte graphique NVIDIA, puis le processeur graphique d'un Mac à puce Apple,
et à défaut le processeur principal (CPU). L'installeur indique dès sa première étape
lequel s'applique.

Sur le CPU seul, VOLUTE fonctionne, mais la segmentation est bien plus lente. Si un
ordinateur mieux équipé est accessible, le travail peut alors se partager. Sur
l'installation la plus lente, placez les points ou les boîtes de chaque séquence sur
quelques trames choisies, en ne vérifiant la prédiction que sur ces trames, puis
enregistrez le projet (**Fichier › Données du Projet › Exporter les données du projet**).
Sur l'ordinateur le plus rapide, avec les mêmes dossiers d'images, **Fichier › Traitement
par lot…** propage alors ces projets dans toute leur séquence et exporte les résultats.
Transmettez le fichier de projet (`.volute`) plutôt que l'état d'inférence (`.voluteinf`) :
ce dernier est expérimental, et son transfert d'une machine ou d'un processeur de calcul à
l'autre n'est pas garanti.

Si une carte NVIDIA reste inutilisée, son pilote est le plus souvent trop ancien :
l'installeur le signale. Mettez le pilote à jour, puis relancez la commande
d'installation, qui remplace ce qu'il faut.

### Sous macOS, le Dock affiche « python » au lieu de VOLUTE

C'est le cas quand VOLUTE est lancé depuis le Terminal. Lancé depuis `VOLUTE.app`, comme
l'installeur le prépare, il affiche son propre nom et son icône.

### Sous macOS, les fenêtres de choix de fichiers restent en anglais alors que VOLUTE est en français

Ces fenêtres sont dessinées par macOS, qui suit la langue du système et non celle de
l'application. Décocher **Sélecteurs de fichiers du système** dans **Fichier ›
Paramètres…**, onglet *Interface*, fait dessiner à VOLUTE les siennes, qui suivent sa
langue ; le changement prend effet au démarrage suivant.

## Utilisation de VOLUTE

### Quel modèle choisir ?

- **SAM2.1 Large** est le plus précis, et celui par lequel commencer.
- **SAM2.1 Small** est plus rapide et un peu moins précis : intéressant sur un ordinateur
  sans carte graphique adaptée, ou pour de longues séquences.
- **SAM2++** est nécessaire pour suivre des **points** plutôt que délimiter des objets ;
  il a aussi un mode masque, comparable à SAM2.
- **MedSAM2** est entraîné sur des images médicales (scanner, IRM, échographie).
  L'installeur le propose sans le cocher par défaut : si vous ne l'avez pas déjà fait lors
  de l'installation initiale, relancez la commande d'installation et choisissez-le. Sur
  une installation faite à la main, voir la documentation de référence, sur GitHub :
  [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#medsam2-setup-optional).
  Il s'utilise avec une **boîte** : tracez d'abord une boîte autour de la structure, puis
  affinez au besoin avec des points positifs ou négatifs ; l'étape 3 du tutoriel,
  [Un premier objet](tutorial/first-object.fr.md#délimiter-la-région-par-une-boîte), le
  montre. Un point seul donne rarement un bon
  résultat, MedSAM2 ayant été conçu pour être guidé par des boîtes.

Aucune règle ne dit à l'avance lequel convient le mieux à un type d'images donné : faire
des essais sur quelques trames et comparer le résultat est le moyen le plus rapide de le
savoir. Le modèle se choisit à chaque démarrage : voir, dans le tutoriel,
[l'étape 1, Choisir un modèle](tutorial/start.fr.md#choisir-un-modèle), et pour SAM2++,
[l'étape 10, Suivre des points avec SAM2++](tutorial/points.fr.md).

### Mes images sont une vidéo : comment les charger ?

**Fichier › Extraire les trames d'une vidéo…** transforme la vidéo en un dossier d'images
numérotées, puis propose de le charger. Cette fonction repose sur ffmpeg, que l'installeur
fournit. Dans le tutoriel : [l'étape 2, Charger les trames](tutorial/load-frames.fr.md).
Dans la documentation de référence, sur GitHub :
[Extracting frames from a video](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#extracting-frames-from-a-video).

### Quelles images VOLUTE peut-il charger, et dans quel ordre ?

Un dossier d'images JPEG, PNG, BMP ou TIFF, toutes de **même taille** : une image par
trame. Elles sont prises dans l'ordre de leurs noms, les nombres étant comparés comme tels :
`trame_2` passe avant `trame_10`. Une image dont le nom se termine par `00000`
est prise comme première trame.

### Le suivi se trompe sur certaines trames : comment le corriger ?

Allez sur une trame où le masque est faux, ajoutez-y des points, positifs dans l'objet
et négatifs en dehors, et relancez la prédiction. Cliquez ensuite sur **Re-propager
depuis cette trame…** : seul cet objet est suivi de nouveau, à partir de cette trame,
sur autant de trames que vous le choisissez. Dans le tutoriel,
[l'étape 6, Suivre les objets dans la vidéo](tutorial/tracking.fr.md) le montre sur un
exemple, de [la correction sur la trame](tutorial/tracking.fr.md#corriger-sur-la-trame)
à [sa re-propagation aux trames voisines](tutorial/tracking.fr.md#reporter-la-correction-sur-les-trames-voisines).
Dans la documentation de référence, sur GitHub, la section
[Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started)
du README résume l'enchaînement complet.

Cette correction est celle à essayer en premier. Si elle ne donne pas un résultat
satisfaisant, les masques peuvent être retouchés à la main : voir
[Peut-on retoucher un masque à la main ?](#peut-on-retoucher-un-masque-à-la-main-)

### Les mêmes points donnent-ils toujours exactement les mêmes masques ?

Presque, mais pas toujours au pixel près. Les modèles n'utilisent pas de hasard pour
prédire, mais leurs calculs, menés en parallèle sur la carte graphique et avec une
précision réduite, n'aboutissent pas toujours aux mêmes arrondis : d'une exécution à
l'autre, un masque peut gagner ou perdre quelques pixels sur ses bords. Les écarts sont un
peu plus grands d'un ordinateur à l'autre (Mac, carte NVIDIA, processeur seul) ou d'une
version de PyTorch à l'autre.

Deux cas méritent attention :

- **Le suivi de points de SAM2++** est plus sensible : un léger écart suffit à décider si
  le point est trouvé ou perdu sur une trame. L'étape 10 du tutoriel en donne un exemple,
  ses versions française et anglaise ayant été capturées lors de deux exécutions
  différentes : voir
  [Le point et les masques ensemble](tutorial/points.fr.md#le-point-et-les-masques-ensemble).
- **L'ordre des prédictions compte.** Sur une trame, SAM2 tient compte du masque qu'il y a
  déjà prédit : poser trois points puis prédire une fois ne donne pas forcément le même
  masque que prédire après chaque point. Un masque recalculé d'un seul coup à partir des
  mêmes points, à la réouverture d'un projet ou dans un traitement par lot, peut donc
  différer légèrement de celui obtenu en séance.

Pour des résultats reproductibles, conservez les fichiers exportés (masques, coordonnées)
plutôt que de compter sur un nouveau calcul, et notez le modèle utilisé.

### Peut-on retoucher un masque à la main ?

Oui : **Fichier › Exporter la trame pour édition…** exporte une trame et ses masques pour
GIMP ou un autre éditeur d'images, et **Fichier › Importer des masques…** récupère les
masques retouchés. GIMP ne s'installe pas avec VOLUTE : téléchargez-le sur
[gimp.org](https://www.gimp.org) (version 3.0 ou ultérieure). Dans le tutoriel :
[Retoucher un masque à la main dans GIMP](tutorial/corrections.fr.md#retoucher-un-masque-à-la-main-dans-gimp),
à l'étape 5. Dans la documentation de référence, sur GitHub :
[GIMP-assisted mask editing](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#gimp-assisted-mask-editing-mask-mode-only).

### La propagation est lente, ou l'ordinateur manque de mémoire

- Utilisez **SAM2.1 Small** au lieu de SAM2.1 Large.
- Dans **Fichier › Paramètres…**, onglet *Performances et outils*, réduisez **Images
  gardées en mémoire**.
- Découpez une très longue séquence en plusieurs séquences plus courtes.

Sans carte graphique adaptée, la propagation reste lente quels que soient les réglages.

### Les masques ont de petits trous, ou un message mentionne « Skipping the post-processing step »

SAM2 comble les petits trous avec un composant qui exige une carte NVIDIA et une étape de
compilation. L'installeur le remplace par un équivalent qui fonctionne partout. Sur une
installation faite à la main, appliquez ce remplacement comme l'explique la documentation
de référence, sur GitHub : [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#optional-cpumps-fallback-patch-for-mask-post-processing).

Avec une carte NVIDIA, le composant d'origine peut aussi être compilé à la main, à condition
de disposer des droits d'administrateur pour installer les outils qu'il demande. Le gain
de vitesse est faible, et les masques restent les mêmes : la solution de remplacement
installée par VOLUTE comble les petits trous de la même façon. Voir la documentation de
référence, sur GitHub :
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#compiling-the-cuda-extension-instead).

### Comment enregistrer mon travail et le reprendre plus tard ?

**Fichier › Données du Projet › Exporter les données du projet** (Ctrl+S, ⌘S sur Mac)
enregistre les objets, points, boîtes et points de référence dans un fichier `.volute`.
Les masques prédits ne sont pas enregistrés : relancer la prédiction ou la propagation les
régénère. Les masques importés, que rien ne pourrait régénérer, sont enregistrés sauf
choix contraire. Dans le tutoriel :
[l'étape 9, Enregistrer, reprendre, traiter par lot](tutorial/project.fr.md). Dans la
documentation de référence, sur GitHub : [Project data management](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#project-data-management).

### Peut-on traiter de nombreuses séquences sans intervenir à chaque étape ?

Oui : **Fichier › Traitement par lot…** parcourt une liste de projets enregistrés, chacun
associé à son dossier d'images, et exporte les résultats. Dans le tutoriel :
[Le traitement par lot](tutorial/project.fr.md#le-traitement-par-lot), à l'étape 9. Dans
la documentation de référence, sur GitHub : [Batch processing](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#batch-processing).

### Comment changer de langue, ou d'autres réglages ?

Le menu **Langue** bascule immédiatement entre français et anglais. Les autres réglages
sont dans **Fichier › Paramètres…** ; ils sont conservés dans le fichier
`volute_config.yaml`, qu'une mise à jour ne modifie pas. Dans le tutoriel :
[l'étape 11, Paramètres, langue, raccourcis](tutorial/settings.fr.md).

## Données, résultats et citation

### Mes données sont-elles envoyées quelque part ?

Non. VOLUTE et les modèles fonctionnent entièrement sur votre ordinateur, et VOLUTE
n'établit aucune connexion réseau : images, masques et résultats n'en sortent jamais.
Autrement dit, si le fait de copier les données sur votre ordinateur (ou d'y accéder
depuis votre ordinateur) est compatible avec les règles concernant ces données, le fait
d'utiliser VOLUTE pour les traiter n'a pas d'incidence.

### Que peut-on exporter ?

Les images avec les masques affichés dessus, les coordonnées des masques, les centroïdes,
les enveloppes convexes, les contours extérieurs, les distances aux points de référence et
les trajectoires des points suivis : sous forme d'images, ou de fichiers JSON, CSV, Excel
(XLSX) ou Pickle. Dans le tutoriel :
[l'étape 8, Exporter les résultats](tutorial/export.fr.md), et pour les points suivis
[Exporter les positions](tutorial/points.fr.md#exporter-les-positions), à l'étape 10. Dans
la documentation de référence, sur GitHub : [Export](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#export).

### Comment citer VOLUTE ?

Citez le modèle utilisé — SAM 2, et MedSAM2 ou SAM 2++ le cas échéant : les références
BibTeX figurent dans **Aide › À propos** et dans la documentation de référence, sur
GitHub : [Credits and acknowledgements](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#credits-and-acknowledgements).
Pour VOLUTE lui-même, citez son dépôt, https://github.com/nicolasaudibert/VOLUTE, avec la
version utilisée, indiquée dans **Aide › À propos**.

### Sous quelle licence VOLUTE est-il distribué ?

La [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html) : VOLUTE
peut être utilisé, étudié, modifié et redistribué librement ; une version modifiée qui est
redistribuée doit rester sous la même licence.

### Où obtenir de l'aide, ou signaler un problème ?

Ouvrez un ticket (*issue*) sur [GitHub](https://github.com/nicolasaudibert/VOLUTE/issues),
en décrivant ce que vous avez fait et ce qui s'est passé. Joignez le message d'erreur s'il
y en a un, et pour un problème d'installation le fichier `install.log` du dossier VOLUTE.
