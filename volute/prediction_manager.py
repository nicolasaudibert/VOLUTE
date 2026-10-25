"""
Prediction Manager
Handles SAM2 predictions and mask propagation
"""

import numpy as np
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from .progress_dialog import AnimatedProgressDialog
from .progress_worker import run_with_progress

def plan_object_spans(cond_frames, num_frames, mode='midpoint', overrides=None):
    """Lay out the propagation spans of one object from its sorted conditioning
    frames.

    Frames before the first conditioning frame come from a backward span, frames
    after the last one from a forward span. Between two consecutive ones, `mode`
    — or overrides[(start, end)] — shares the frames out: each mask over its
    half by default, the first mask only with 'forward', the second only with
    'backward'.

    Returns (spans, segments): spans as (first_frame, last_frame, reverse) in
    running order, segments as the entries of
    ObjectManager.object_propagation_segments.
    """
    overrides = overrides or {}
    spans, segments = [], []
    if cond_frames[0] > 0:
        spans.append((cond_frames[0], 0, True))
    for start, end in zip(cond_frames, cond_frames[1:]):
        seg_mode = overrides.get((start, end), mode)
        if seg_mode == 'forward':
            junction = end - 1
        elif seg_mode == 'backward':
            junction = start
        else:
            junction = (start + end) // 2
        if seg_mode != 'backward':
            spans.append((start, junction, False))
        if seg_mode != 'forward':
            spans.append((end, junction + 1, True))
        segments.append({'start': start, 'end': end, 'mode': seg_mode, 'junction': junction})
    if cond_frames[-1] < num_frames - 1:
        spans.append((cond_frames[-1], num_frames - 1, False))
    return spans, segments


class PredictionManager:
    """Manages SAM2 predictions and propagation"""

    def __init__(self, main_window):
        self.main_window = main_window
        # Spans left by an interrupted propagation, kept so that the next one
        # can resume them: {'plan', 'groups', 'state', 'fingerprint', 'obj_ids',
        # 'frame', 'reverse'}, or None
        self._interrupted = None

    def _maybe_clip(self, obj_id, frame_idx, mask):
        """Clip a predicted mask to the object's box when strict clipping is on.

        Variant 'box_frames' clips only the frames that carry a box, leaving
        propagated frames untouched; variant 'reference_box' falls back to the
        object's reference box everywhere else. Applied before store_mask, so
        centroid, hull and contour all describe the clipped mask — which also
        makes the clipping irreversible (see README).
        """
        om = self.main_window.object_manager
        if not om.strict_box_clipping:
            return mask
        box = om.get_box(obj_id, frame_idx)
        if box is None and om.box_clipping_mode == 'reference_box':
            box = om.get_reference_box(obj_id)
        if box is None:
            return mask
        return om.clip_mask_to_box(mask, box)

    def _consume_propagation(self, obj_ids, start_frame_idx, reverse, report, is_cancelled,
                             frames_processed, max_frames=None, progress_max=None):
        """Consume one propagation span for a group of objects: store every mask
        it yields for them — or, in point mode, every tracked point — and report
        progress. Runs in a worker thread, report and is_cancelled being those
        run_with_progress hands to its task.

        progress_max caps the value reported to the dialog, for the bounded spans
        of repropagate_object_from_frame.

        Returns the updated frame count, whether the person cancelled, and the
        last frame stored (None if none was).
        """
        om = self.main_window.object_manager
        backend = self.main_window.sam2_backend
        point_mode = self._is_point_mode()
        last_frame = None
        try:
            if point_mode:
                results = backend.propagate_point_tracks(
                    start_frame_idx, reverse=reverse, max_frame_num_to_track=max_frames)
            else:
                results = backend.propagate_masks(
                    start_frame_idx, reverse=reverse, max_frame_num_to_track=max_frames)
            for result in results:
                frame_idx = result[0]
                if point_mode:
                    for cur_obj_id, coord in result[1].items():
                        if cur_obj_id in obj_ids:
                            om.object_tracked_points.setdefault(cur_obj_id, {})[frame_idx] = coord
                else:
                    out_obj_ids, out_mask_logits = result[1], result[2]
                    for i, cur_obj_id in enumerate(out_obj_ids):
                        if cur_obj_id not in obj_ids or i >= out_mask_logits.shape[0]:
                            continue
                        mask = backend.process_mask_output(out_mask_logits[i])
                        mask = self._maybe_clip(cur_obj_id, frame_idx, mask)
                        om.store_mask(cur_obj_id, frame_idx, mask)

                last_frame = frame_idx
                frames_processed += 1
                report(frames_processed if progress_max is None
                       else min(frames_processed, progress_max))
                if is_cancelled():
                    return frames_processed, True, last_frame
        except Exception as e:
            if self.main_window.debug_mode:
                direction = "backward" if reverse else "forward"
                print(f"Error during {direction} propagation for objects {list(obj_ids)}: {e}")
        return frames_processed, False, last_frame

    def predict_current_image(self):
        """Predict masks for all objects with prompts (points and/or box) on current image"""
        if not self.main_window.image_manager.has_images():
            self.main_window.ui_manager.show_message("warning",
                                       self.main_window.localization.get_text("warning"),
                                       self.main_window.localization.get_text("no_image_loaded"))
            return

        # Get objects with prompts
        objects_with_points = self.main_window.object_manager.get_objects_with_prompts(
            self.main_window.image_manager.current_image_idx
        )

        if not objects_with_points:
            self.main_window.ui_manager.show_message("warning", 
                                       self.main_window.localization.get_text("warning"), 
                                       self.main_window.localization.get_text("define_points_first"))
            return
        
        try:
            if self._is_point_mode():
                self._predict_tracked_points()
                return
            # Show progress dialog
            progress_dialog = AnimatedProgressDialog(
                self.main_window.localization.get_text("prediction_in_progress"), 
                self.main_window.localization.get_text("cancel"), 
                0, 100, self.main_window,
                configurable_pacing=True
            )
            progress_dialog.setWindowTitle(self.main_window.localization.get_text("prediction"))
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.show()
            progress_dialog.setValue(5)
            QApplication.processEvents()
            
            successful_predictions = 0

            def _predict(report, is_cancelled):
                nonlocal successful_predictions
                # Initialize inference state if needed
                if not self.main_window.sam2_backend.inference_state:
                    report(10, self.main_window.localization.get_text("initializing_inference_state"))
                    self.main_window.sam2_backend.init_inference_state(
                        self.main_window.image_manager.current_folder
                    )
            
                # Process each object
                image_info = self.main_window.image_manager.get_current_image_info()
                h, w = image_info['height'], image_info['width']
                for obj_idx, obj_id in enumerate(objects_with_points):
                    if is_cancelled():
                        return False
                
                    # Update progress
                    base_progress = 20 + (obj_idx * 70) // len(objects_with_points)
                    obj_name = self.main_window.object_manager.object_names.get(obj_id, f"Object {obj_id}")
                    report(base_progress,
                           self.main_window.localization.get_text("predicting_object", obj_name))
                
                    # Get points and box for SAM2
                    points, labels = self.main_window.object_manager.get_points_for_sam(
                        obj_id, self.main_window.image_manager.current_image_idx, w, h
                    )
                    box = self.main_window.object_manager.get_box_for_sam(
                        obj_id, self.main_window.image_manager.current_image_idx, w, h
                    )

                    if len(points) == 0 and box is None:
                        continue

                    try:
                        # Mask-based initialization: resend the stored mask
                        # before add_new_points_or_box, which would otherwise silently
                        # discard it — only on the first point-based predict call for a
                        # mask-imported frame not yet point-corrected.
                        om = self.main_window.object_manager
                        frame_idx = self.main_window.image_manager.current_image_idx
                        # Correction tracking: a mask already present on this frame before
                        # this predict call means the upcoming prediction is a correction
                        # of already-tracked data, not a first-time initialization.
                        had_mask_before = frame_idx in om.object_masks.get(obj_id, {})
                        if frame_idx in om.mask_imported_frames.get(obj_id, set()):
                            stored_mask = om.object_masks.get(obj_id, {}).get(frame_idx)
                            if stored_mask is not None:
                                self.main_window.sam2_backend.add_mask(frame_idx, obj_id, stored_mask)
                            om.mask_imported_frames[obj_id].discard(frame_idx)

                        # Predict mask
                        out_obj_ids, out_mask_logits = self.main_window.sam2_backend.predict_mask(
                            self.main_window.image_manager.current_image_idx, obj_id, points, labels,
                            box=box
                        )
                    
                        # Process results
                        if out_mask_logits is not None and len(out_obj_ids) > 0:
                            # Find our object in results
                            obj_index = None
                            for i, returned_obj_id in enumerate(out_obj_ids):
                                if returned_obj_id == obj_id:
                                    obj_index = i
                                    break
                        
                            if obj_index is not None and obj_index < out_mask_logits.shape[0]:
                                # Process mask
                                mask_logits = out_mask_logits[obj_index]
                                mask = self.main_window.sam2_backend.process_mask_output(mask_logits)
                                mask = self._maybe_clip(obj_id, frame_idx, mask)

                                # Store mask
                                self.main_window.object_manager.store_mask(
                                    obj_id, self.main_window.image_manager.current_image_idx, mask
                                )
                                om.object_predicted_frames.setdefault(obj_id, set()).add(frame_idx)
                                if had_mask_before:
                                    om.object_corrected_frames.setdefault(obj_id, set()).add(frame_idx)

                            
                                successful_predictions += 1
                            
                                if self.main_window.debug_mode:
                                    print(f"Successful prediction for {obj_name}")
                            else:
                                if self.main_window.debug_mode:
                                    print(f"Cannot find mask for object {obj_id} in results")
                        else:
                            if self.main_window.debug_mode:
                                print(f"No mask generated for object {obj_id}")
                
                    except Exception as e:
                        if self.main_window.debug_mode:
                            print(f"Error predicting mask for object {obj_id}: {e}")
                        continue
                return True

            if not run_with_progress(progress_dialog, _predict):
                progress_dialog.close()
                if self.main_window.debug_mode:
                    print("Prediction cancelled by user")
                return
            
            # Close progress dialog
            progress_dialog.setValue(100)
            progress_dialog.close()
            
            # Update display
            self.main_window.display_manager.update_display(maintain_global_zoom=True)
            
            # Show result message
            if successful_predictions > 0:
                message = self.main_window.localization.get_text("prediction_successful", 
                                                   successful_predictions, 
                                                   self.main_window.image_manager.current_image_idx + 1)
                self.main_window.ui_manager.show_message("info", self.main_window.localization.get_text("success"), message)
            else:
                self.main_window.ui_manager.show_message("warning", 
                                           self.main_window.localization.get_text("warning"), 
                                           self.main_window.localization.get_text("no_masks_generated"))
        
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            error_msg = self.main_window.localization.get_text("prediction_error", e)
            if self.main_window.debug_mode:
                print(error_msg)
                import traceback
                traceback.print_exc()
            self.main_window.ui_manager.show_message("error", self.main_window.localization.get_text("error"), error_msg)
    
    def propagate_masks(self):
        """Propagate masks — or, in point mode, tracked points — through the
        entire video, from every annotated frame of each object"""
        om = self.main_window.object_manager
        backend = self.main_window.sam2_backend
        point_mode = self._is_point_mode()
        if point_mode:
            obj_ids = [obj_id for obj_id, frames in om.object_tracked_points.items() if frames]
        else:
            obj_ids = list(om.get_objects_with_masks())

        if not self.main_window.image_manager.has_images() or not obj_ids \
                or not backend.inference_state:
            self.main_window.ui_manager.show_message("warning",
                                       self.main_window.localization.get_text("warning"),
                                       self.main_window.localization.get_text("no_inference_state"))
            return
        
        try:
            if self.main_window.debug_mode:
                print(f"Propagating objects: {obj_ids}")

            plan = groups = None
            record = self._interrupted
            if record is not None and record['state'] is backend.inference_state:
                choice = self._ask_resume(record)
                if choice is None:
                    return
                if choice == 'resume':
                    groups = record['groups']
                    plan = []
                    for group_idx, group_obj_ids, first, last, reverse in record['plan']:
                        kept = tuple(o for o in group_obj_ids if o in om.object_colors)
                        if kept:
                            plan.append((group_idx, kept, first, last, reverse))
            if plan is None:
                planned = self._plan_propagation(obj_ids)
                if planned is None:
                    return
                plan, groups = planned
            self._interrupted = None

            # Calculate progress
            total_operations = sum(abs(last - first) + 1 for _, _, first, last, _ in plan)
            
            progress_dialog = AnimatedProgressDialog(
                self.main_window.localization.get_text("propagation_in_progress"), 
                self.main_window.localization.get_text("cancel"), 
                0, max(total_operations, 1), self.main_window,
                configurable_pacing=True
            )
            progress_dialog.setWindowTitle(self.main_window.localization.get_text("prediction"))
            progress_dialog.setWindowModality(Qt.WindowModal)
            # Spans of different groups cover the same frames, so progress can
            # reach the maximum before the work ends; with auto-reset the dialog
            # would then hide and give the main window back while the worker
            # still uses SAM2
            progress_dialog.setAutoClose(False)
            progress_dialog.setAutoReset(False)
            progress_dialog.show()
            
            frames_processed = 0
            was_cancelled = False
            stopped_at = None
            
            def _propagate(report, is_cancelled):
                nonlocal frames_processed, was_cancelled, stopped_at

                for span_idx, (_, group_obj_ids, first, last, reverse) in enumerate(plan):
                    report(label=self.main_window.localization.get_text(
                        "backward_propagation" if reverse else "forward_propagation",
                        self._group_label(group_obj_ids)))

                    frames_processed, was_cancelled, last_done = self._consume_propagation(
                        group_obj_ids, first, reverse, report, is_cancelled, frames_processed,
                        max_frames=abs(last - first))
                    if was_cancelled:
                        stopped_at = (span_idx, last_done)
                        return

            run_with_progress(progress_dialog, _propagate)
            
            # Close progress dialog
            progress_dialog.close()
            
            # Update display
            self.main_window.display_manager.update_display()
            
            # Show result message
            if was_cancelled:
                self._record_interruption(plan, groups, *stopped_at)
                message = self.main_window.localization.get_text("propagation_cancelled", frames_processed)
                self.main_window.ui_manager.show_message(
                "info", self.main_window.localization.get_text("propagation_interrupted"), message)
            else:
                results = om.object_tracked_points if point_mode else om.object_masks
                total_results = sum(len(frames) for frames in results.values())
                message = self.main_window.localization.get_text(
                    "point_propagation_successful" if point_mode else "propagation_successful",
                    total_results, len(obj_ids))
                self.main_window.ui_manager.show_message("info", self.main_window.localization.get_text("success"), message)
        
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            error_msg = self.main_window.localization.get_text("propagation_error", e)
            if self.main_window.debug_mode:
                print(error_msg)
                import traceback
                traceback.print_exc()
            self.main_window.ui_manager.show_message("error", self.main_window.localization.get_text("error"), error_msg)

    def _register_annotated_frames(self, obj_id):
        """
        Register with SAM2 every annotated frame of an object that it does not
        hold as a conditioning frame — after a project load, for instance, only
        one prompted frame per object is replayed. In mask mode the stored mask
        is sent through add_mask, byte-identical to the original conditioning;
        a frame with points or a box but no stored mask, as a predicted frame
        after a project load, is predicted again from them, and an object with
        masks but neither an annotated nor a conditioning frame is conditioned
        on its first mask. In point mode the frame's first positive point is
        registered again.
        """
        om = self.main_window.object_manager
        backend = self.main_window.sam2_backend
        held = set(backend.get_conditioning_frames(obj_id))
        frames = om.get_annotated_frames(obj_id)
        if self._is_point_mode():
            image_info = self.main_window.image_manager.get_current_image_info()
            for frame_idx in frames:
                positive = om.object_points[obj_id][frame_idx].get('positive')
                if frame_idx in held or not positive:
                    continue
                x, y = positive[0]
                try:
                    backend.predict_point_track(
                        frame_idx, obj_id,
                        (int(x * image_info['width']), int(y * image_info['height'])))
                except Exception as e:
                    if self.main_window.debug_mode:
                        print(f"Error registering frame {frame_idx} of point {obj_id}: {e}")
            return
        if not frames:
            masks = om.object_masks.get(obj_id)
            if held or not masks:
                return
            frames = [min(masks)]
        image_info = self.main_window.image_manager.get_current_image_info()
        for frame_idx in frames:
            if frame_idx in held:
                continue
            stored_mask = om.object_masks.get(obj_id, {}).get(frame_idx)
            try:
                if stored_mask is not None:
                    backend.add_mask(frame_idx, obj_id, stored_mask)
                    continue
                w, h = image_info['width'], image_info['height']
                points, labels = om.get_points_for_sam(obj_id, frame_idx, w, h)
                box = om.get_box_for_sam(obj_id, frame_idx, w, h)
                if len(points) == 0 and box is None:
                    continue
                out_obj_ids, out_mask_logits = backend.predict_mask(
                    frame_idx, obj_id, points, labels, box=box)
                for i, out_obj_id in enumerate(out_obj_ids):
                    if out_obj_id == obj_id and i < out_mask_logits.shape[0]:
                        mask = backend.process_mask_output(out_mask_logits[i])
                        om.store_mask(obj_id, frame_idx, self._maybe_clip(obj_id, frame_idx, mask))
                        om.object_predicted_frames.setdefault(obj_id, set()).add(frame_idx)
            except Exception as e:
                if self.main_window.debug_mode:
                    print(f"Error registering frame {frame_idx} of object {obj_id}: {e}")

    def _plan_propagation(self, obj_ids):
        """
        Register every annotated frame with SAM2, ask how to share out the
        frames between consecutive conditioning frames when an object has
        several, and lay out the propagation.

        Objects with the same conditioning frames and the same junctions share
        their spans: SAM2 tracks every object at each frame anyway, so one pass
        serves them all. Returns (plan, groups) — the spans to run as
        (group_idx, obj_ids, first_frame, last_frame, reverse), and per group its
        objects and frame count — or None if the person cancelled.
        """
        om = self.main_window.object_manager
        backend = self.main_window.sam2_backend
        config = self.main_window.config_manager
        total_frames = len(self.main_window.image_manager.image_paths)

        cond_frames = {}
        for obj_id in obj_ids:
            self._register_annotated_frames(obj_id)
            frames = backend.get_conditioning_frames(obj_id)
            if frames:
                cond_frames[obj_id] = frames

        mode, overrides = config.get_junction_mode(), {}
        several = {obj_id: frames for obj_id, frames in cond_frames.items() if len(frames) > 1}
        if several and config.ask_junction_mode():
            from .dialogs import JunctionModeDialog
            dialog = JunctionModeDialog(several, om.object_names, mode, self._is_point_mode(),
                                        self.main_window.localization, self.main_window)
            if not dialog.exec_():
                return None
            mode, overrides, dont_ask = dialog.get_choice()
            if dont_ask:
                config.set('propagation.junction_mode', mode)
                config.set('propagation.ask_junction_mode', False)
                config.save_config()

        layouts = {}
        for obj_id, frames in cond_frames.items():
            obj_overrides = {(start, end): seg_mode
                             for (oid, start, end), seg_mode in overrides.items() if oid == obj_id}
            spans, segments = plan_object_spans(frames, total_frames, mode, obj_overrides)
            om.object_propagation_segments[obj_id] = segments
            layouts.setdefault(tuple(spans), []).append(obj_id)

        plan, groups = [], []
        for group_idx, (spans, group_obj_ids) in enumerate(layouts.items()):
            group_obj_ids = tuple(group_obj_ids)
            plan.extend((group_idx, group_obj_ids) + span for span in spans)
            groups.append({'obj_ids': group_obj_ids,
                           'total': sum(abs(last - first) + 1 for first, last, _ in spans)})
        return plan, groups

    def _group_label(self, obj_ids, limit=3):
        """Names of a group's objects, the first `limit` of them followed by
        an ellipsis when there are more."""
        names = [self.main_window.object_manager.object_names.get(o, f"Object {o}")
                 for o in obj_ids]
        label = ", ".join(names[:limit])
        return label + ", \u2026" if len(names) > limit else label

    def _prompt_fingerprint(self):
        """What a propagation depends on, compared to tell whether anything
        changed since one was interrupted: the prompts SAM2 holds, the points
        and boxes, and the set of objects."""
        om = self.main_window.object_manager
        points = sorted(
            (obj_id, frame_idx, tuple(p.get('positive', ())), tuple(p.get('negative', ())))
            for obj_id, frames in om.object_points.items()
            for frame_idx, p in frames.items()
            if p.get('positive') or p.get('negative'))
        boxes = sorted((obj_id, frame_idx, tuple(box))
                       for obj_id, frames in om.object_boxes.items()
                       for frame_idx, box in frames.items())
        return (self.main_window.sam2_backend.conditioning_revision,
                tuple(sorted(om.object_colors)), tuple(points), tuple(boxes))

    def _record_interruption(self, plan, groups, span_idx, last_done):
        """Keep the spans an interrupted propagation had left, starting with
        what remains of the one it stopped in. SAM2 keeps the memory of the
        frames already tracked, so resuming them gives the same masks as an
        uninterrupted run."""
        group_idx, obj_ids, first, last, reverse = plan[span_idx]
        remaining = list(plan[span_idx + 1:])
        if last_done is None:
            remaining.insert(0, plan[span_idx])
        elif last_done != last:
            remaining.insert(0, (group_idx, obj_ids,
                                 last_done + (-1 if reverse else 1), last, reverse))
        self._interrupted = {
            'plan': remaining,
            'groups': groups,
            'state': self.main_window.sam2_backend.inference_state,
            'fingerprint': self._prompt_fingerprint(),
            'obj_ids': obj_ids,
            'frame': first if last_done is None else last_done,
            'reverse': reverse,
        }

    def _ask_resume(self, record):
        """Offer to resume an interrupted propagation or start it over; returns
        'resume', 'restart', or None when the person cancels."""
        from .dialogs import ask_resume_propagation
        left = {}
        for group_idx, _, first, last, _ in record['plan']:
            left[group_idx] = left.get(group_idx, 0) + abs(last - first) + 1
        passes = [(self._group_label(group['obj_ids']),
                   group['total'] - left.get(group_idx, 0), group['total'])
                  for group_idx, group in enumerate(record['groups'])]
        return ask_resume_propagation(
            self.main_window, self.main_window.localization,
            self._group_label(record['obj_ids']),
            record['frame'] + 1, record['reverse'], passes,
            modified=record['fingerprint'] != self._prompt_fingerprint())

    def repropagate_object_from_frame(self, obj_id, frame_idx, forward_frames=None, backward_frames=None):
        """
        Re-propagate a single object's masks from an already-corrected frame,
        overwriting existing masks in the given span (explicit action, not
        triggered automatically by a correction point).

        Unlike propagate_masks(), this does not reset the SAM2 backend state:
        the correction point on frame_idx has already been registered against
        the live inference_state through the ordinary point-add flow, so SAM2
        already treats it as a correction against prev_sam_mask_logits.

        forward_frames / backward_frames: None means unbounded in that
        direction (propagate to the end/start of the video).
        """
        if not self.main_window.sam2_backend.inference_state:
            self.main_window.ui_manager.show_message(
                "warning",
                self.main_window.localization.get_text("warning"),
                self.main_window.localization.get_text("no_inference_state"))
            return

        total_frames = len(self.main_window.image_manager.image_paths)
        fwd_count = forward_frames if forward_frames is not None else (total_frames - 1 - frame_idx)
        bwd_count = backward_frames if backward_frames is not None else frame_idx
        total_operations = max(fwd_count, 0) + max(bwd_count, 0)

        progress_dialog = AnimatedProgressDialog(
            self.main_window.localization.get_text("propagation_in_progress"),
            self.main_window.localization.get_text("cancel"),
            0, max(total_operations, 1), self.main_window,
            configurable_pacing=True
        )
        progress_dialog.setWindowTitle(self.main_window.localization.get_text("prediction"))
        progress_dialog.setWindowModality(Qt.WindowModal)
        # The backward span also yields its starting frame, so progress reaches
        # the maximum one frame early; with auto-reset the dialog would then
        # hide and give the main window back while the worker still uses SAM2
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.show()

        obj_name = self.main_window.object_manager.object_names.get(obj_id, f"Object {obj_id}")
        frames_processed = 0
        was_cancelled = False

        def _run_span(report, is_cancelled, reverse, span_frames, count):
            nonlocal frames_processed, was_cancelled
            if count <= 0 or was_cancelled:
                return
            report(label=self.main_window.localization.get_text(
                "repropagation_backward" if reverse else "repropagation_forward", obj_name))
            frames_processed, was_cancelled, _ = self._consume_propagation(
                {obj_id}, frame_idx, reverse, report, is_cancelled, frames_processed,
                max_frames=span_frames, progress_max=total_operations)

        def _repropagate(report, is_cancelled):
            _run_span(report, is_cancelled, False, forward_frames, fwd_count)
            _run_span(report, is_cancelled, True, backward_frames, bwd_count)

        run_with_progress(progress_dialog, _repropagate)

        # The re-propagated frames change SAM2's memory: an interrupted
        # propagation can still resume, with the dialog reporting a change
        if self._interrupted is not None:
            self._interrupted['fingerprint'] = None

        progress_dialog.close()
        self.main_window.object_manager.object_corrected_frames.get(obj_id, set()).discard(frame_idx)
        self.main_window.display_manager.update_display(maintain_global_zoom=True)

        if was_cancelled:
            message = self.main_window.localization.get_text("propagation_cancelled", frames_processed)
            self.main_window.ui_manager.show_message(
                "info", self.main_window.localization.get_text("propagation_interrupted"), message)

    # ------------------------------------------------------------------
    # Point tracking helpers (SAM2++ point mode)
    # ------------------------------------------------------------------
    
    def _is_point_mode(self):
        """Return True when the backend is SAM2++ configured in point task."""
        b = self.main_window.sam2_backend
        return (getattr(b, 'is_sam2plus', False) and
                getattr(b, 'sam2plus_task', 'mask') == 'point')
    
    def _predict_tracked_points(self):
        """Predict initial point tracks for all objects with positive points (point mode)."""
        from PyQt5.QtCore import Qt
    
        frame_idx = self.main_window.image_manager.current_image_idx
        objects_with_points = self.main_window.object_manager.get_objects_with_points(frame_idx)
        if not objects_with_points:
            self.main_window.ui_manager.show_message(
                "warning",
                self.main_window.localization.get_text("warning"),
                self.main_window.localization.get_text("define_points_first"),
            )
            return
    
        image_info = self.main_window.image_manager.get_current_image_info()
        w, h = image_info['width'], image_info['height']
    
        if not self.main_window.sam2_backend.inference_state:
            self.main_window.sam2_backend.init_inference_state(
                self.main_window.image_manager.current_folder
            )
    
        progress = AnimatedProgressDialog(
            self.main_window.localization.get_text("prediction_in_progress"),
            self.main_window.localization.get_text("cancel"),
            0, len(objects_with_points), self.main_window,
            configurable_pacing=True
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
    
        ok_count = 0
        om = self.main_window.object_manager
    
        def _predict(report, is_cancelled):
            nonlocal ok_count
            for idx, obj_id in enumerate(objects_with_points):
                if is_cancelled():
                    break
                report(idx)
    
                pos = om.object_points[obj_id][frame_idx]['positive']
                if not pos:
                    continue
                norm_x, norm_y = pos[0]
                px, py = int(norm_x * w), int(norm_y * h)
    
                try:
                    out_obj_ids, out_heatmaps = self.main_window.sam2_backend.predict_point_track(
                        frame_idx, obj_id, (px, py)
                    )
                    for i, ret_id in enumerate(out_obj_ids):
                        if ret_id == obj_id and i < len(out_heatmaps):
                            coord = self.main_window.sam2_backend._extract_point_from_heatmap(out_heatmaps[i])
                            if coord is not None:
                                if obj_id not in om.object_tracked_points:
                                    om.object_tracked_points[obj_id] = {}
                                om.object_tracked_points[obj_id][frame_idx] = coord
                                om.object_predicted_frames.setdefault(obj_id, set()).add(frame_idx)
                                ok_count += 1
                except Exception as e:
                    if self.main_window.debug_mode:
                        print(f"Point track prediction error (obj {obj_id}): {e}")

        run_with_progress(progress, _predict)
    
        progress.setValue(len(objects_with_points))
        progress.close()
        self.main_window.display_manager.update_display(maintain_global_zoom=True)
    
        if ok_count > 0:
            self.main_window.ui_manager.show_message(
                "info",
                self.main_window.localization.get_text("success"),
                self.main_window.localization.get_text(
                    "prediction_successful", ok_count, frame_idx + 1
                ),
            )
    
