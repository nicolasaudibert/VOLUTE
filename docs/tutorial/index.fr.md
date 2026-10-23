# Tutoriel

*[English version](index.md)*

Ce tutoriel parcourt VOLUTE pas à pas, sur un exemple réel : une courte vidéo d'IRM
dynamique (aussi appelée IRM en temps réel) d'une personne qui parle. Il suppose seulement
que VOLUTE est installé — voir les guides pour [Windows](../install-windows.fr.md),
[macOS](../install-macos.fr.md) et [Linux](../install-linux.fr.md) — et aucune
connaissance en programmation.

![Quatre trames de la vidéo d'exemple, avec le conduit vocal en bleu et la langue en orange sur chacune](images/fr/tracking-propagated.webp)

## L'exemple

La vidéo montre une coupe médiosagittale[^coupe] de la tête, pendant qu'un locuteur
prononce la phrase *Le filou et la fripouille* : on y voit bouger les lèvres, la langue,
le voile du palais[^voile] et le pharynx[^pharynx]. Elle dure 2,2 secondes et compte 111
images, 50 par seconde. Chacune de ces images s'appelle une **trame**.

Pour les utilisateurs non-spécialistes des sciences de la parole, les termes anatomiques
utilisés dans ce tutoriel sont explicités de façon simplifiée par des notes de bas de
page.

**Téléchargez-la avant de commencer :** [nancy_P1_S1_excerpt.mp4](nancy_P1_S1_excerpt.mp4)
(430 Ko). Enregistrez-la à un endroit facile à retrouver, le Bureau par exemple.

La vidéo est un extrait d'un corpus enregistré à Nancy par Karyna Isaieva et collègues, et
placé dans le domaine public par ses auteurs :

> Isaieva K., Laprie Y., Leclère J., Douros I. K., Felblinger J., Vuissoz P.-A. (2021).
> Multimodal dataset of real-time 2D and static 3D MRI of healthy French speakers.
> *Scientific Data* 8, 258. Données sur
> [figshare](https://springernature.figshare.com/collections/Multimodal_dataset_of_real-time_2D_and_static_3D_MRI_of_healthy_French_speakers/5270387),
> sous licence CC0.

La façon dont l'extrait a été tiré des données d'origine et converti en vidéo MP4 est
décrite dans
[make_excerpt.py](https://github.com/nicolasaudibert/VOLUTE/blob/main/tutorial/make_excerpt.py)
(en anglais).

## Les étapes

1. [Avant de commencer](start.fr.md) : lancer VOLUTE, choisir un modèle, se repérer
   dans la fenêtre.
2. [Charger les trames](load-frames.fr.md) : transformer la vidéo en images, et passer
   de l'une à l'autre.
3. [Un premier objet](first-object.fr.md) : délimiter le conduit vocal sur une trame,
   par une boîte puis des points.
4. [Plusieurs objets](objects.fr.md) : ajouter la langue, délimitée par une boîte
   seule.
5. [Corriger les masques](corrections.fr.md) : repérer les structures considérées à tort
   comme faisant partie du conduit vocal, corriger la détection par des points, et
   retoucher à la main dans GIMP.
6. [Suivre les objets dans la vidéo](tracking.fr.md) : propager les masques à toutes les
   trames, vérifier le suivi, et le corriger là où il se trompe.
7. [Affichage et points de référence](display.fr.md) : contours, centres de gravité et
   autres réglages d'affichage, puis repères pour mesurer des distances.
8. [Exporter les résultats](export.fr.md) : les images avec leurs masques, les
   coordonnées, et les distances des masques aux points de référence.
9. [Enregistrer, reprendre, traiter par lot](project.fr.md) : le fichier projet, sa
   réouverture, et son traitement sans un clic.
10. [Suivre des points avec SAM2++](points.fr.md) : suivre l'apex lingual, puis le combiner
    avec les masques.
11. [Paramètres, langue, raccourcis](settings.fr.md) : adapter VOLUTE à ses habitudes.

Chaque étape prend quelques minutes. Les copies d'écran viennent d'un Mac ; sous Windows
ou Linux les fenêtres ont un aspect un peu différent, mais les mêmes boutons se trouvent
aux mêmes endroits.

[^coupe]: Coupe selon le plan qui sépare la tête en deux moitiés, droite et gauche, en passant par son milieu : l'image montre ainsi les organes de la parole de profil.
[^voile]: Partie arrière, molle et mobile, du palais. En s'abaissant, il ouvre le passage entre le pharynx et les fosses nasales ; en se relevant, il le ferme.
[^pharynx]: Conduit situé en arrière de la cavité buccale et des fosses nasales, qui descend jusqu'au larynx.
