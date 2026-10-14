# Installer VOLUTE sous macOS

*[English version](install-macos.md)*

Ce guide s'adresse à qui n'a jamais installé de programme Python et ne tape que rarement,
voire jamais, de commandes. Il suffit de copier une ligne, de la coller dans une fenêtre
et de répondre à une question : l'installeur fait le reste.

Rien d'autre n'est modifié sur le Mac. VOLUTE dispose de son propre dossier, avec sa
propre copie de Python : un Python, Anaconda ou Miniconda déjà installé n'est pas
touché, et il n'est pas nécessaire de savoir s'il y en a un. Aucun mot de passe n'est
demandé, et aucun outil de développement n'est nécessaire.

Les messages de l'installeur sont en anglais ; ce guide explique chacun d'eux.

## Avant de commencer

- **macOS 11 (Big Sur) ou plus récent.**
- **Environ 10 Go d'espace disque libre**, et une connexion à Internet. L'installation
  télécharge plusieurs gigaoctets ; comptez de 20 à 60 minutes selon la connexion.
- **Le processeur du Mac** change la vitesse, pas la marche à suivre : l'installeur le
  détecte de lui-même. Pour le connaître, ouvrez le menu Apple, en haut à gauche de
  l'écran, puis **À propos de ce Mac** :
  - **Puce : Apple M1, M2, M3…** — VOLUTE utilise le processeur graphique du Mac, et va
    relativement vite ;
  - **Processeur : … Intel …** — VOLUTE fonctionne, mais la segmentation est nettement
    plus lente.

## 1. Ouvrir le Terminal

Le Terminal est la fenêtre dans laquelle on tape des commandes.

1. Appuyez sur **Commande (⌘) + Espace** pour ouvrir Spotlight, tapez `Terminal`, puis
   appuyez sur **Entrée**. (Le Terminal se trouve aussi dans **Applications ›
   Utilitaires**.)

Une fenêtre s'ouvre, avec une ligne qui se termine par `%`, comme
`monNomUtilisateur@MacBook ~ %`. C'est sur cette ligne que se tapent les commandes.

## 2. Coller la commande d'installation

1. Sélectionnez toute la ligne ci-dessous et copiez-la (⌘ + C), ou cliquez sur le bouton
   de copie à droite du cadre :

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_macos.sh)"
   ```

2. Cliquez dans la fenêtre du Terminal, puis collez avec **⌘ + V**.
3. Appuyez sur **Entrée**.

## 3. Répondre à l'installeur

L'installeur installe d'abord **Miniforge**, la distribution de Python sur laquelle
VOLUTE fonctionne : une barre de signes `#` montre le téléchargement, et l'installation
prend une à deux minutes. Il affiche ensuite ce qu'il a détecté sur le Mac, par exemple :

```
[1/8] Checking the computer
    Darwin 24.6.0, arm64
    Mac with Apple Silicon: GPU acceleration (MPS)
    Installation folder: /Users/monNomUtilisateur/VOLUTE
```

c'est-à-dire le système, le type de processeur et le dossier d'installation, puis il
demande quels **modèles** préentrainés télécharger. Un modèle est l'intelligence
artificielle qui réalise la segmentation ; il en faut au moins un.

```
    Models to download (more can be added later by running the installer again):
     * 1. SAM2.1 Large - best accuracy (900 MB)
       2. SAM2.1 Small - faster, slightly less accurate (185 MB)
       3. SAM2++ - needed for point tracking (800 MB)
       4. MedSAM2 - medical images: CT, MRI, ultrasound, 4 models (625 MB)
       a. All of the above (2510 MB)
    Numbers of the models to download, separated by spaces, or a for all [1]:
```

Les quatre choix sont : SAM2.1 Large, le plus précis ; SAM2.1 Small, plus rapide et un
peu moins précis ; SAM2++, nécessaire au suivi de points ; MedSAM2, quatre variantes de
SAM2 entraînées sur des images médicales (scanner, IRM, échographie).

- Pour garder le choix proposé, marqué d'un `*`, appuyez simplement sur **Entrée**.
- Pour en choisir d'autres, tapez leurs numéros séparés par des espaces, puis Entrée :
  `1 3` télécharge SAM2.1 Large et SAM2++. Pour tous les télécharger, tapez `a`. Sur un
  Mac Intel, `2` seul, le modèle le plus rapide, mérite d'être envisagé.

Dans le doute, appuyez sur Entrée : d'autres modèles pourront être ajoutés plus tard.

L'installeur demande enfin `Start the installation? [Y/n]` (« Lancer l'installation ? ») :
appuyez sur **Entrée** pour accepter.

## 4. Patienter

L'installeur travaille maintenant seul, en huit étapes numérotées de `[1/8]` à `[8/8]`.
Des lignes défilent, parfois avec des barres de progression ; les étapes les plus longues
peuvent rester quelques minutes sur la même ligne. C'est normal : laissez la fenêtre
ouverte, et le Mac allumé.

L'installation est terminée quand s'affiche :

```
======================================================================
VOLUTE 0.9.3 is installed.
======================================================================
```

avec le numéro de la version du moment. Le Terminal peut alors être fermé (⌘ + Q).

## 5. Lancer VOLUTE

VOLUTE se trouve dans le dossier **Applications** de votre dossier personnel — et non dans
le dossier Applications principal, qui demanderait un mot de passe d'administrateur.

1. Dans le Finder, choisissez **Aller › Départ** (⇧ + ⌘ + H), puis ouvrez **Applications**.
2. Double-cliquez sur **VOLUTE**. Pour l'avoir sous la main, faites-le glisser dans le
   Dock.

Spotlight le trouve aussi : ⌘ + Espace, puis tapez `VOLUTE`.

VOLUTE demande d'abord quel modèle utiliser : choisissez-en un que vous avez téléchargé.
Si macOS demande si VOLUTE peut accéder à votre dossier **Documents**, **Bureau** ou
**Téléchargements**, cliquez sur **Autoriser** : sans quoi VOLUTE ne peut pas lire les
images qui s'y trouvent.

La section [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started) du README guide une première
session.

ffmpeg, qui permet d'extraire les trames d'une vidéo (**Fichier › Extraire les trames
d'une vidéo…**), est installé avec VOLUTE. GIMP, qui sert à retoucher les masques à la
main, ne l'est pas : s'il vous est utile, installez-le depuis
[gimp.org](https://www.gimp.org) (version 3.0 ou ultérieure).

## Ce que contient le dossier VOLUTE

- `miniforge3` : la distribution Python de VOLUTE et son environnement ;
- `SAM2-Plus` : le code des modèles, dont VOLUTE fait partie (`SAM2-Plus/tools`), et les
  modèles téléchargés (`SAM2-Plus/checkpoints`). Il porte ce nom quels que soient les
  modèles choisis : SAM2-Plus fournit aussi le code de SAM2 ;
- `install.log` : le journal de l'installation.

Rien n'y est à modifier à la main : les réglages se changent dans
**Fichier › Paramètres…**.

## Mettre à jour VOLUTE, ou ajouter un modèle

Refaites les **étapes 1 et 2**. L'installation existante est reconnue :

- VOLUTE est mis à jour vers sa dernière version, et vos réglages sont conservés ;
- la liste des modèles indique ceux déjà téléchargés (`already downloaded`) ; appuyez sur
  **Entrée** pour n'en ajouter aucun, ou tapez les numéros de ceux à ajouter. Quand tous
  sont déjà téléchargés, la question n'est pas posée ;
- rien de ce qui est déjà installé n'est retéléchargé : une mise à jour prend quelques
  minutes.

Si une installation a été interrompue — connexion perdue, fenêtre fermée —, refaire les
étapes 1 et 2 la reprend là où elle s'était arrêtée.

## Désinstaller

1. Placez le dossier **VOLUTE** de votre dossier personnel dans la Corbeille.
2. Placez **VOLUTE**, dans le dossier Applications de votre dossier personnel, dans la
   Corbeille.

Rien d'autre n'a été installé.

## En cas de problème

**L'installation s'est arrêtée sur une ligne `ERROR:`.** Lisez la ligne : elle indique
quoi faire. Le plus souvent, la connexion a été coupée pendant un téléchargement :
refaites les étapes 1 et 2, et l'installation reprend. Si le problème persiste, le fichier
`install.log` du dossier VOLUTE retrace chaque étape ; c'est lui qu'il faut joindre à une
demande d'aide.

**Le Terminal répond `command not found` ou `parse error`.** La ligne n'a pas été collée
en entier. Copiez-la de nouveau avec le bouton de copie, et collez-la une seconde fois.

**Le téléchargement est très lent, ou échoue à chaque fois.** Certains réseaux
d'établissement filtrent les téléchargements volumineux. Essayez depuis un autre réseau, ou
demandez au service informatique d'autoriser `github.com`, `conda-forge.org`,
`download.pytorch.org`, `pypi.org`, `files.pythonhosted.org`, `dl.fbaipublicfiles.com` et
`huggingface.co`.

**VOLUTE ne s'ouvre pas, ou affiche une alerte au démarrage.** L'alerte cite la fin du
journal que VOLUTE tient dans `~/Library/Logs/VOLUTE.log` (dans le Finder : **Aller ›
Aller au dossier…**, puis collez ce chemin). C'est ce message qu'il faut joindre à une
demande d'aide.

**VOLUTE ne peut pas ouvrir les images de Documents, du Bureau ou de Téléchargements.**
L'accès a sans doute été refusé quand macOS l'a demandé. Ouvrez **Réglages Système ›
Confidentialité et sécurité › Fichiers et dossiers**, trouvez VOLUTE, et autorisez les
dossiers concernés.

La [FAQ](faq.fr.md) répond aux questions les plus courantes.
Pour une installation pas à pas à la main, voir [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md) (en anglais).
