# 6. Suivre les objets dans la vidéo

*[English version](tracking.md)*

Les deux objets sont maintenant délimités sur la trame 1, et leurs masques corrigés.
Cette étape les suit dans toute la vidéo, puis corrige le suivi là où il se trompe.

## Propager les masques

Revenez à la trame 1. Dans l'onglet **Prédiction**, cliquez sur **Propager les masques
sur toute la vidéo** : VOLUTE suit le conduit vocal et la langue d'une trame à l'autre,
jusqu'à la fin de la vidéo. Pour le conduit vocal, le suivi part du masque retouché dans
GIMP à l'étape 5.

<img src="images/fr/tracking-progress.webp" alt="La fenêtre de progression, pendant la propagation des masques" width="262">

Cela prend environ trois minutes et demie sur un Mac récent ou avec une carte graphique
NVIDIA, et davantage sans : les objets sont suivis l'un après l'autre. À la fin, VOLUTE
indique combien de masques il a générés : cliquez sur **OK**.

Parcourez les trames avec le curseur : les masques suivent la langue et les lèvres dans
leurs mouvements. Les points et les boîtes n'apparaissent que sur la trame 1, où ils ont
été placés.

![Les trames 1, 38, 75 et 111, chacune avec le conduit vocal et la langue](images/fr/tracking-propagated.webp)

La propagation part de la trame affichée. Lancée depuis une trame au milieu de la vidéo,
elle avance jusqu'à la fin, puis revient en arrière jusqu'au début.

## Vérifier le suivi

Le suivi n'est pas infaillible : il faut parcourir les trames pour repérer celles où un
masque se trompe. Pour examiner un contour de près, agrandissez la région qui vous
intéresse avec l'outil de zoom, sous l'image
(voir l'[étape 1](start.fr.md#se-repérer-dans-la-fenêtre)) : VOLUTE garde ce zoom quand
on change de trame, et le premier de ces outils revient à l'image entière.

Allez à la trame 63, cliquez sur **Langue** dans la liste des objets de l'onglet
**Objets**, et zoomez sur la racine de la langue et le pharynx. Si les noms des objets
cachent le contour, décochez **Afficher les étiquettes** dans l'onglet **Prédiction**
(voir l'[étape 7](display.fr.md)). Le masque de la langue déborde en arrière, sur l'air
du pharynx, qui appartient au conduit vocal.

<img src="images/fr/tracking-error.webp" alt="La trame 63 agrandie, où le masque de la langue déborde sur l'air du pharynx" width="450">

Sur les trames voisines, le masque de la langue suit bien son bord : l'erreur se limite à
cette trame et à ses environs.

## Corriger sur la trame

La correction se fait comme sur la trame 1 à l'étape 5. **Langue** étant sélectionnée,
faites un clic droit dans la bande d'air que le masque de la langue recouvre à tort, puis
prédisez depuis l'onglet **Prédiction**. Le masque de la langue revient au bord de la
langue.

<img src="images/fr/tracking-corrected.webp" alt="La trame 63 agrandie, le masque de la langue revenu au bord de la langue, avec le point négatif" width="450">

Au bas de la région agrandie, une petite zone d'air sombre n'est plus couverte par aucun
des deux masques : sur cette trame, le conduit vocal ne s'étend pas jusque-là. Un clic
gauche dans cette zone, **Conduit vocal** étant sélectionné, suivi d'une prédiction, la
lui rattacherait de la même façon.

## Reporter la correction sur les trames voisines

La correction n'a modifié que le masque de la trame 63. Dans l'onglet **Prédiction**,
cliquez sur **Re-propager depuis cette trame…** : seul l'objet sélectionné est suivi de
nouveau, à partir de la trame affichée, et les autres objets gardent leurs masques.

La fenêtre demande jusqu'où aller. **Illimité** va jusqu'à la fin de la vidéo vers
l'avant, et jusqu'à son début vers l'arrière ; un nombre de trames limite la
re-propagation. L'erreur ne s'étendant pas au-delà de quelques trames, indiquez `5` dans
**Avant (trames)** et dans **Arrière (trames)**, puis cliquez sur **OK**.

<img src="images/fr/tracking-repropagate-dialog.webp" alt="La fenêtre Empan de re-propagation, avec 5 trames vers l'avant et 5 vers l'arrière" width="218">

Les trames 58 à 68 sont suivies de nouveau en tenant compte de la correction, et le reste
de la vidéo demeure inchangé. Les points de toutes les trames sont pris en compte
ensemble.

**Propager les masques sur toute la vidéo** prendrait aussi la correction en compte, mais
suivrait de nouveau tous les objets, dans toute la vidéo. **Re-propager depuis cette
trame…** est plus rapide, et ne touche ni aux autres objets ni aux trames situées hors de
l'empan choisi.

Précédent : [5. Corriger les masques](corrections.fr.md) · Suite : [7. Affichage et points de référence](display.fr.md)
