# Installer VOLUTE sous Linux

*[English version](install-linux.md)*

Ce guide s'adresse à qui n'a jamais installé de programme Python et ne tape que rarement,
voire jamais, de commandes. Il suffit de copier une ligne, de la coller dans un terminal
et de répondre à une question : l'installeur fait le reste.

Rien d'autre n'est modifié sur l'ordinateur. VOLUTE dispose de son propre dossier, avec
sa propre copie de Python : le Python du système, Anaconda ou Miniconda, s'ils sont
installés, ne sont pas touchés. Aucun mot de passe n'est demandé : l'installation ne
nécessite pas de droits d'administrateur.

Les messages de l'installeur sont en anglais ; ce guide explique chacun d'eux.

## Avant de commencer

- **Ubuntu 22.04 ou 24.04**, sur un PC 64 bits (processeur Intel ou AMD). VOLUTE peut
  fonctionner sur d'autres distributions, mais seule Ubuntu a été testée.
- **Environ 10 Go d'espace disque libre**, et une connexion à Internet. L'installation
  télécharge plusieurs gigaoctets ; comptez de 20 à 60 minutes selon la connexion.
- **Une carte graphique NVIDIA rend VOLUTE bien plus rapide**, et l'installeur la détecte
  de lui-même, à condition que son pilote NVIDIA soit installé. Pour le vérifier, ouvrez
  **Logiciels et mises à jour**, onglet **Pilotes additionnels** : le pilote coché doit
  être un pilote NVIDIA, de préférence celui marqué *recommandé*. Si vous en changez,
  redémarrez l'ordinateur avant d'installer VOLUTE. Sans carte NVIDIA, VOLUTE fonctionne
  aussi, mais plus lentement.

## 1. Ouvrir un terminal

Le terminal est la fenêtre dans laquelle on tape des commandes.

1. Appuyez sur **Ctrl + Alt + T**. (Le terminal se trouve aussi parmi les applications :
   cliquez sur **Afficher les applications**, en bas du dock, puis tapez `Terminal`.)

Une fenêtre s'ouvre, avec une ligne qui se termine par `$`, comme
`monNomUtilisateur@monOrdinateur:~$`. C'est sur cette ligne que se tapent les commandes.

## 2. Coller la commande d'installation

1. Sélectionnez toute la ligne ci-dessous et copiez-la (Ctrl + C), ou cliquez sur le
   bouton de copie à droite du cadre :

   ```bash
   bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
   ```

2. Cliquez dans la fenêtre du terminal, puis collez avec **Ctrl + Maj + V** : dans un
   terminal, Ctrl + V seul ne colle pas.
3. Appuyez sur **Entrée**.

Si le terminal répond `Command 'curl' not found`, `curl` n'est pas installé sur cet
ordinateur : utilisez plutôt cette ligne, qui fait la même chose avec `wget` :

```bash
bash -c "$(wget -qO- https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
```

## 3. Répondre à l'installeur

L'installeur installe d'abord **Miniforge**, la distribution de Python sur laquelle
VOLUTE fonctionne : une barre montre le téléchargement, et l'installation prend une à
deux minutes. Il affiche ensuite ce qu'il a détecté sur l'ordinateur, par exemple :

```
[1/8] Checking the computer
    Ubuntu 24.04.1 LTS (Linux 6.8.0-45-generic), x86_64
    NVIDIA GPU of compute capability 8.6, driver supporting CUDA 12.8: PyTorch for CUDA 12.8
    Installation folder: /home/monNomUtilisateur/VOLUTE
```

c'est-à-dire le système, la carte graphique trouvée et le dossier d'installation. Sans
carte NVIDIA, la deuxième ligne indique
`No NVIDIA GPU found: CPU only, so segmentation will be slow`.

Il demande ensuite quels **modèles** préentrainés télécharger. Un modèle est
l'intelligence artificielle qui réalise la segmentation ; il en faut au moins un.

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
  `1 3` télécharge SAM2.1 Large et SAM2++. Pour tous les télécharger, tapez `a`. Sans
  carte NVIDIA, `2` seul, le modèle le plus rapide, mérite d'être envisagé.

Dans le doute, appuyez sur Entrée : d'autres modèles pourront être ajoutés plus tard.

L'installeur demande enfin `Start the installation? [Y/n]` (« Lancer l'installation ? ») :
appuyez sur **Entrée** pour accepter.

## 4. Patienter

L'installeur travaille maintenant seul, en huit étapes numérotées de `[1/8]` à `[8/8]`.
Des lignes défilent, parfois avec des barres de progression ; les étapes les plus longues
peuvent rester quelques minutes sur la même ligne. C'est normal : laissez la fenêtre
ouverte, et l'ordinateur allumé.

À la dernière étape, une petite fenêtre vide s'ouvre et se referme aussitôt : l'installeur
vérifie que VOLUTE pourra ouvrir ses fenêtres.

L'installation est terminée quand s'affiche :

```
======================================================================
VOLUTE 0.9.4 is installed.
======================================================================
```

avec le numéro de la version du moment. Le terminal peut alors être fermé.

## 5. Lancer VOLUTE

VOLUTE figure parmi les applications, comme les autres programmes :

1. Cliquez sur **Afficher les applications**, en bas du dock, ou appuyez sur la touche
   **Super** (celle qui porte le logo Windows sur la plupart des claviers).
2. Tapez `VOLUTE`, puis cliquez sur son icône.

Pour l'avoir sous la main, une fois VOLUTE ouvert, faites un clic droit sur son icône dans
le dock et choisissez **Épingler au Dash** (**Ajouter aux favoris** sous Ubuntu 22.04).

VOLUTE demande d'abord quel modèle utiliser : choisissez-en un que vous avez téléchargé.

La section [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started) du README guide une première
session.

ffmpeg, qui permet d'extraire les trames d'une vidéo (**Fichier › Extraire les trames
d'une vidéo…**), est installé avec VOLUTE. GIMP, qui sert à retoucher les masques à la
main, ne l'est pas : s'il vous est utile, installez **GIMP 3.0 ou ultérieur**, depuis le
**Centre d'applications** d'Ubuntu (paquet Snap) ou depuis [Flathub](https://flathub.org/apps/org.gimp.GIMP)
(paquet Flatpak). VOLUTE trouve l'un comme l'autre. La version de GIMP qu'installe
`apt install gimp` sous Ubuntu 22.04 et 24.04 est la 2.10, que VOLUTE ne peut pas
utiliser. Avec le paquet Snap, enregistrez les fichiers échangés avec GIMP dans votre
dossier personnel ou sur un support amovible : le paquet Snap n'a pas accès au reste du
disque.

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

Collez dans un terminal la ligne suivante, puis appuyez sur Entrée :

```bash
rm -rf ~/VOLUTE ~/.local/share/applications/volute.desktop
```

Elle supprime le dossier **VOLUTE** de votre dossier personnel et l'entrée de VOLUTE
parmi les applications. Rien d'autre n'a été installé.

## En cas de problème

**L'installation s'est arrêtée sur une ligne `ERROR:`.** Lisez la ligne : elle indique
quoi faire. Le plus souvent, la connexion a été coupée pendant un téléchargement :
refaites les étapes 1 et 2, et l'installation reprend. Si le problème persiste, le fichier
`install.log` du dossier VOLUTE retrace chaque étape ; c'est lui qu'il faut joindre à une
demande d'aide.

**Le terminal répond `syntax error`, ou n'affiche rien après le collage.** La ligne n'a
pas été collée en entier, ou pas du tout. Copiez-la de nouveau avec le bouton de copie,
et collez-la avec Ctrl + Maj + V.

**L'erreur indique `Qt could not open a window`.** Une bibliothèque du système manque à
l'affichage des fenêtres ; les lignes au-dessus la nomment. Joignez `install.log` à une
demande d'aide.

**Le téléchargement est très lent, ou échoue à chaque fois.** Certains réseaux
d'établissement filtrent les téléchargements volumineux. Essayez depuis un autre réseau, ou
demandez au service informatique d'autoriser `github.com`, `conda-forge.org`,
`download.pytorch.org`, `pypi.org`, `files.pythonhosted.org`, `dl.fbaipublicfiles.com` et
`huggingface.co`.

**Le message indique que la carte graphique n'est pas utilisée alors que l'ordinateur a
une carte NVIDIA.** Soit son pilote n'est pas installé (`No NVIDIA GPU found`), soit il est
trop ancien (`NVIDIA driver too old`) ; l'installeur installe alors une version qui
fonctionne sans la carte. Installez ou mettez à jour le pilote (voir *Avant de
commencer*), redémarrez, puis refaites les étapes 1 et 2.

**VOLUTE ne s'ouvre pas depuis les applications.** Lancez-le depuis un terminal, qui
affiche ses messages :

```bash
~/VOLUTE/SAM2-Plus/tools/launchers/volute.sh
```

C'est le message affiché qu'il faut joindre à une demande d'aide.

La [FAQ](faq.fr.md) répond aux questions les plus courantes.
Pour une installation pas à pas à la main, sous une autre distribution par exemple, voir
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md) (en anglais).
