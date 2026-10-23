# Tutorial

*[Version française](index.fr.md)*

This tutorial walks through VOLUTE one step at a time, on a real example: a short dynamic
MRI video (also called real-time MRI) of a person speaking. It assumes only that VOLUTE is
installed — see the guides for [Windows](../install-windows.md),
[macOS](../install-macos.md) and [Linux](../install-linux.md) — and no knowledge of
programming.

![Four frames of the example video, with the vocal tract in blue and the tongue in orange on each](images/en/tracking-propagated.webp)

## The example

The video shows a midsagittal slice[^coupe] of the head, while a speaker says the
sentence *Le filou et la fripouille*, "the rascal and the scoundrel": lips, tongue, soft
palate[^voile] and pharynx[^pharynx] are seen moving. It lasts 2.2 seconds and holds 111
images, 50 per second. Each of these images is called a **frame**.

For readers who are not speech scientists, the anatomical terms used in this tutorial are
explained, in simplified form, in footnotes.

**Download it before starting:** [nancy_P1_S1_excerpt.mp4](nancy_P1_S1_excerpt.mp4)
(430 KB). Save it somewhere easy to find, such as the Desktop.

The video is an excerpt of a corpus recorded in Nancy, France, by Karyna Isaieva and
colleagues, and placed in the public domain by its authors:

> Isaieva K., Laprie Y., Leclère J., Douros I. K., Felblinger J., Vuissoz P.-A. (2021).
> Multimodal dataset of real-time 2D and static 3D MRI of healthy French speakers.
> *Scientific Data* 8, 258. Data on
> [figshare](https://springernature.figshare.com/collections/Multimodal_dataset_of_real-time_2D_and_static_3D_MRI_of_healthy_French_speakers/5270387),
> under CC0.

How the excerpt was made from the original data and converted to an MP4 video is described
in
[make_excerpt.py](https://github.com/nicolasaudibert/VOLUTE/blob/main/tutorial/make_excerpt.py).

## The steps

1. [Before you start](start.md): starting VOLUTE, choosing a model, finding your way
   around the window.
2. [Loading the frames](load-frames.md): turning the video into images, and moving
   from one to the next.
3. [A first object](first-object.md): outlining the vocal tract on one frame, with a box
   then points.
4. [Several objects](objects.md): adding the tongue, outlined with a box alone.
5. [Correcting masks](corrections.md): spotting the structures wrongly taken as part of
   the vocal tract, correcting the outline with points, and retouching by hand in GIMP.
6. [Following the objects through the video](tracking.md): propagating the masks to every
   frame, checking the tracking, and correcting it where it goes wrong.
7. [Display and reference points](display.md): contours, centroids and other display
   settings, then landmarks for measuring distances.
8. [Exporting the results](export.md): images with their masks, coordinates, and the
   distances from the masks to the reference points.
9. [Saving, resuming, batch processing](project.md): the project file, opening it again,
   and running it without a click.
10. [Following points with SAM2++](points.md): tracking the tongue apex, then combining
   it with the masks.
11. [Settings, language, shortcuts](settings.md): adapting VOLUTE to one's habits.

Each step takes a few minutes. The screenshots come from a Mac; on Windows or Linux the
windows look slightly different, but the same buttons are in the same places.

[^coupe]: A slice along the plane that divides the head into left and right halves through its middle: the image thus shows the speech organs in profile.
[^voile]: The back part of the palate, soft and mobile. Lowered, it opens the passage between the pharynx and the nasal cavity; raised, it closes it.
[^pharynx]: The tube behind the oral and nasal cavities, which runs down to the larynx.
