# Installer VOLUTE sous Windows

*[English version](install-windows.md)*

Ce guide s'adresse à qui n'a jamais installé de programme Python et ne tape que rarement,
voire jamais, de commandes. Il suffit de copier une ligne, de la coller dans une fenêtre
et de répondre à une question : l'installeur fait le reste.

Rien d'autre n'est modifié sur l'ordinateur. VOLUTE dispose de son propre dossier, avec
sa propre copie de Python : un Python, Anaconda ou Miniconda déjà installé n'est
pas touché, et il n'est pas nécessaire de savoir s'il y en a un d'installé.

Les messages de l'installeur sont en anglais ; ce guide explique chacun d'eux.

## Avant de commencer

- **Windows 10 ou 11, en 64 bits.** C'est le cas de presque tous les PC vendus depuis dix
  ans.
- **Environ 10 Go d'espace disque libre**, et une connexion à Internet. L'installation
  télécharge plusieurs gigaoctets ; comptez de 20 à 60 minutes selon la connexion.
- **Aucun droit d'administrateur** n'est nécessaire.
- **Une carte graphique NVIDIA rend VOLUTE bien plus rapide**, et l'installeur la détecte
  de lui-même. Pour savoir si l'ordinateur en a une, ouvrez le Gestionnaire des tâches
  (Ctrl + Maj + Échap), allez dans l'onglet **Performances** et cherchez une ligne **GPU**
  qui mentionne NVIDIA. Si c'est le cas, mieux vaut d'abord mettre son pilote à jour :
  ouvrez **NVIDIA App** ou **GeForce Experience** s'ils sont installés, ou téléchargez le
  pilote sur [nvidia.com/drivers](https://www.nvidia.com/fr-fr/drivers/). Sans carte
  NVIDIA, VOLUTE fonctionne aussi, mais plus lentement.

## 1. Ouvrir PowerShell

PowerShell est la fenêtre dans laquelle on tape des commandes.

1. Cliquez sur le bouton **Démarrer**, et tapez `PowerShell`.
2. Cliquez sur **Windows PowerShell**. Attention, **ne faites pas** de clic droit suivi de
   *Exécuter en tant qu'administrateur* : aucun droit d'administrateur n'est nécessaire
   (voir plus haut), et cela poserait problème ensuite pour l'accès à certains dossiers.

Une fenêtre à fond bleu foncé ou noir s'ouvre, avec une ligne qui se termine par `>`,
comme `PS C:\Users\monNomUtilisateur>`. C'est sur cette ligne que se tapent les commandes.

## 2. Coller la commande d'installation

1. Sélectionnez toute la ligne ci-dessous et copiez-la (Ctrl + C), ou cliquez sur le
   bouton de copie à droite du cadre :

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_windows.ps1 | iex"
   ```

2. Cliquez dans la fenêtre PowerShell, puis collez d'un **clic droit** (ou avec Ctrl + V).
3. Appuyez sur **Entrée**.

## 3. Répondre à l'installeur

L'installeur installe d'abord **Miniforge**, la distribution de Python sur laquelle
VOLUTE fonctionne, ce qui prend quelques minutes. Il affiche ensuite ce qu'il a détecté
sur l'ordinateur, par exemple :

```
[1/8] Checking the computer
    Windows 10, AMD64
    NVIDIA GPU of compute capability 8.6, driver supporting CUDA 12.8: PyTorch for CUDA 12.8
    Installation folder: C:\Users\monNomUtilisateur\VOLUTE
```

c'est-à-dire le système, la carte graphique trouvée et le dossier d'installation, puis il
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
  `1 3` télécharge SAM2.1 Large et SAM2++. Pour tous les télécharger, tapez `a`.

Dans le doute, appuyez sur Entrée : d'autres modèles pourront être ajoutés plus tard.

L'installeur demande enfin `Start the installation? [Y/n]` (« Lancer l'installation ? ») :
appuyez sur **Entrée** pour accepter.

## 4. Patienter

L'installeur travaille maintenant seul, en huit étapes numérotées de `[1/8]` à `[8/8]`.
Des lignes défilent, parfois avec des barres de progression ; l'étape la plus longue est
**PyTorch**, qui peut rester plusieurs minutes sur la même ligne. C'est normal : laissez
la fenêtre ouverte, et l'ordinateur allumé.

L'installation est terminée quand s'affiche :

```
======================================================================
VOLUTE 0.9.3 is installed.
======================================================================
```

avec le numéro de la version du moment, suivi de `Press Enter to close` (« Appuyez sur
Entrée pour fermer »). Appuyez sur Entrée : la fenêtre se ferme.

## 5. Lancer VOLUTE

Double-cliquez sur l'icône **VOLUTE** du Bureau.

Une fenêtre noire s'ouvre d'abord, puis la fenêtre de VOLUTE, qui demande quel modèle
utiliser : choisissez-en un que vous avez téléchargé. **Laissez la fenêtre noire ouverte**
pendant le travail : elle fait partie de VOLUTE, et la fermer ferme l'application. Si
VOLUTE s'arrête à cause d'un problème, cette fenêtre reste ouverte et affiche un message
qui l'explique.

La section [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started) du README guide une première
session.

ffmpeg, qui permet d'extraire les trames d'une vidéo (**Fichier › Extraire les trames
d'une vidéo…**), est installé avec VOLUTE. GIMP, qui sert à retoucher les masques à la
main, ne l'est pas : s'il vous est utile, installez-le depuis
[gimp.org](https://www.gimp.org) (version 3.0 ou ultérieure).

## Ce que contient le dossier VOLUTE

- `miniforge3` : la distribution Python de VOLUTE et son environnement ;
- `SAM2-Plus` : le code des modèles, dont VOLUTE fait partie (`SAM2-Plus\tools`), et les
  modèles téléchargés (`SAM2-Plus\checkpoints`). Il porte ce nom quels que soient les
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

1. Supprimez le dossier **VOLUTE** : `C:\Users\<votre nom>\VOLUTE`, ou `C:\VOLUTE` (voir
   plus bas).
2. Supprimez le raccourci **VOLUTE** du Bureau.

Rien d'autre n'a été installé.

## En cas de problème

**L'installation s'est arrêtée sur une ligne `Error` en rouge ou `ERROR:`.** Lisez la
ligne : elle indique quoi faire. Le plus souvent, la connexion a été coupée pendant un
téléchargement : refaites les étapes 1 et 2, et l'installation reprend. Si le problème
persiste, le fichier `install.log` du dossier VOLUTE retrace chaque étape ; c'est lui
qu'il faut joindre à une demande d'aide.

**Le dossier d'installation est `C:\VOLUTE` et non dans mon dossier personnel.** C'est le
cas quand le nom d'utilisateur contient des espaces ou des lettres accentuées
(`C:\Users\Prénom Nom`, `C:\Users\Hélène`), que les outils Python sur lesquels repose
VOLUTE gèrent mal. Cela ne change rien à l'usage.

**Le téléchargement est très lent, ou échoue à chaque fois.** Certains réseaux
d'établissement filtrent les téléchargements volumineux. Essayez depuis un autre réseau, ou
demandez au service informatique d'autoriser `github.com`, `conda-forge.org`,
`download.pytorch.org`, `pypi.org`, `files.pythonhosted.org`, `dl.fbaipublicfiles.com` et
`huggingface.co`.

**Un antivirus signale l'installation, ou la ralentit beaucoup.** L'installeur écrit des
milliers de petits fichiers, que certains antivirus examinent un par un. L'installation ne
devrait pas être considérée comme présentant un risque de sécurité ; si l'antivirus la
bloque, adressez-vous au service informatique.

**Le message indique que la carte graphique n'est pas utilisée alors que l'ordinateur a
une carte NVIDIA.** Le pilote est sans doute trop ancien : l'installeur le signale alors
(`NVIDIA driver too old`), et installe une version qui fonctionne sans la carte. Mettez le
pilote à jour (voir *Avant de commencer*), puis refaites les étapes 1 et 2.

**La fenêtre noire affiche une erreur au lancement de VOLUTE.** Notez le message, ou
faites-en une capture d'écran : il indique ce qui ne va pas, et c'est lui qu'il faut
joindre à une demande d'aide.

La [FAQ](faq.fr.md) répond aux questions les plus courantes.
Pour une installation pas à pas à la main, voir [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md) (en anglais).
