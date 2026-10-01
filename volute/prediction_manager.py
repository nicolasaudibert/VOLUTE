"""
Prediction Manager
Handles SAM2 predictions and mask propagation
"""

import numpy as np
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from .progress_dialog import AnimatedProgressDialog
from .progress_worker import run_with_progress

class PredictionManager:
    """Manages SAM2 predictions and propagation"""

    def __init__(self, main_window):
        self.main_window = main_window

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

    def _consume_propagation(self, obj_id, start_frame_idx, reverse, report, is_cancelled,
                             frames_processed, max_frames=None, skip_existing=False,
                             progress_max=None):
        """Consume one propagation span for one object: store every mask it yields
        and report progress. Runs in a worker thread, report and is_cancelled
        being those run_with_progress hands to its task.

        skip_existing leaves frames that already carry a mask untouched — the
        backward pass must not overwrite what the forward pass produced.
        progress_max caps the value reported to the dialog, for the bounded spans
        of repropagate_object_from_frame.

        Returns the updated frame count and whether the person cancelled.
        """
        om = self.main_window.object_manager
        backend = self.main_window.sam2_backend
        try:
            for frame_idx, out_obj_ids, out_mask_logits in backend.propagate_masks(
                start_frame_idx, reverse=reverse, max_frame_num_to_track=max_frames
            ):
                for i, cur_obj_id in enumerate(out_obj_ids):
                    if cur_obj_id != obj_id or i >= out_mask_logits.shape[0]:
                        continue
                    if skip_existing and frame_idx in om.object_masks.get(cur_obj_id, {}):
                        continue
                    mask = backend.process_mask_output(out_mask_logits[i])
                    mask = self._maybe_clip(cur_obj_id, frame_idx, mask)
                    om.store_mask(cur_obj_id, frame_idx, mask)

                frames_processed += 1
                report(frames_processed if progress_max is None
                       else min(frames_processed, progress_max))
                if is_cancelled():
                    return frames_processed, True
        except Exception as e:
            if self.main_window.debug_mode:
                direction = "backward" if reverse else "forward"
                print(f"Error during {direction} propagation for object {obj_id}: {e}")
        return frames_processed, False

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
        """Propagate masks through entire video"""
        # Check if we have masks to propagate
        objects_with_masks = self.main_window.object_manager.get_objects_with_masks()
        om = self.main_window.object_manager
        has_tracked = (self._is_point_mode() and
                       om.object_tracked_points and
                       any(om.object_tracked_points.values()))
        
        if not self.main_window.image_manager.has_images() or \
                (not objects_with_masks and not has_tracked):
            self.main_window.ui_manager.show_message("warning",
                                       self.main_window.localization.get_text("warning"),
                                       self.main_window.localization.get_text("no_inference_state"))
            return
        
        try:
            if self._is_point_mode():
                self._propagate_point_tracks()
                return
            if not self.main_window.sam2_backend.inference_state:
                self.main_window.ui_manager.show_message("warning", 
                                           self.main_window.localization.get_text("warning"), 
                                           self.main_window.localization.get_text("no_inference_state"))
                return
            
            if self.main_window.debug_mode:
                print(f"Propagating masks for objects: {list(objects_with_masks.keys())}")
            
            # Calculate progress
            total_frames = len(self.main_window.image_manager.image_paths)
            total_operations = sum(total_frames for _ in objects_with_masks)
            
            progress_dialog = AnimatedProgressDialog(
                self.main_window.localization.get_text("propagation_in_progress"), 
                self.main_window.localization.get_text("cancel"), 
                0, total_operations, self.main_window,
                configurable_pacing=True
            )
            progress_dialog.setWindowTitle(self.main_window.localization.get_text("prediction"))
            progress_dialog.setWindowModality(Qt.WindowModal)
            # Each backward pass also yields its starting frame, so progress
            # reaches the maximum before the work ends; with auto-reset the dialog
            # would then hide and give the main window back while the worker
            # still uses SAM2
            progress_dialog.setAutoClose(False)
            progress_dialog.setAutoReset(False)
            progress_dialog.show()
            
            frames_processed = 0
            was_cancelled = False
            
            def _propagate(report, is_cancelled):
                nonlocal frames_processed, was_cancelled

                # Forward propagation for all objects
                for obj_id, start_frame_idx in objects_with_masks.items():
                    if was_cancelled:
                        break
                
                    obj_name = self.main_window.object_manager.object_names.get(obj_id, f"Object {obj_id}")
                    report(label=self.main_window.localization.get_text(
                        "forward_propagation", obj_name))
                
                    frames_processed, was_cancelled = self._consume_propagation(
                        obj_id, start_frame_idx, False, report, is_cancelled, frames_processed)
                    if was_cancelled:
                        break
            
                # Backward propagation for objects that don't start at frame 0
                if not was_cancelled:
                    for obj_id, start_frame_idx in objects_with_masks.items():
                        if was_cancelled or start_frame_idx == 0:
                            continue
                    
                        obj_name = self.main_window.object_manager.object_names.get(obj_id, f"Object {obj_id}")
                        report(label=self.main_window.localization.get_text(
                            "backward_propagation", obj_name))
                    
                        # Reset SAM2 state and recreate conditions
                        self.main_window.sam2_backend.reset_state()
                        self.main_window.sam2_backend.init_inference_state(
                            self.main_window.image_manager.current_folder
                        )
                    
                        # Re-add points for this object
                        self.recreate_object_points(obj_id)
                    
                        frames_processed, was_cancelled = self._consume_propagation(
                            obj_id, start_frame_idx, True, report, is_cancelled, frames_processed,
                            skip_existing=True)
                        if was_cancelled:
                            break

            run_with_progress(progress_dialog, _propagate)
            
            # Close progress dialog
            progress_dialog.close()
            
            # Update display
            self.main_window.display_manager.update_display()
            
            # Show result message
            if was_cancelled:
                message = self.main_window.localization.get_text("propagation_cancelled", frames_processed)
                self.main_window.ui_manager.show_message(
                "info", self.main_window.localization.get_text("propagation_interrupted"), message)
            else:
                total_masks = sum(len(masks) for masks in self.main_window.object_manager.object_masks.values())
                message = self.main_window.localization.get_text("propagation_successful", 
                                                   total_masks, 
                                                   len(objects_with_masks))
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

    def recreate_object_points(self, obj_id):
        """
        Recreate an object's conditioning frames in the SAM2 backend, ahead of
        backward propagation from a freshly reset inference state.

        A frame with an already-stored mask (regardless of whether it came from
        points-only prediction, mask import, or mask+point refinement) is replayed
        directly via add_mask — simpler, byte-identical to the original
        conditioning, and sidesteps the mask/point ordering constraint entirely.
        Frames with points but no stored mask (should not normally occur) fall
        back to the previous points-based replay.
        """
        om = self.main_window.object_manager
        if obj_id not in om.object_points and obj_id not in om.object_masks:
            return

        image_info = self.main_window.image_manager.get_current_image_info()
        if not image_info:
            return

        h, w = image_info['height'], image_info['width']

        point_frames = set(om.object_points.get(obj_id, {}).keys())
        mask_frames  = set(om.object_masks.get(obj_id, {}).keys())

        for frame_idx in sorted(point_frames | mask_frames):
            stored_mask = om.object_masks.get(obj_id, {}).get(frame_idx)
            try:
                if stored_mask is not None:
                    self.main_window.sam2_backend.add_mask(frame_idx, obj_id, stored_mask)
                else:
                    points, labels = om.get_points_for_sam(obj_id, frame_idx, w, h)
                    if len(points) > 0:
                        self.main_window.sam2_backend.predict_mask(frame_idx, obj_id, points, labels)
            except Exception as e:
                if self.main_window.debug_mode:
                    print(f"Error recreating conditioning for object {obj_id} on frame {frame_idx}: {e}")

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
            frames_processed, was_cancelled = self._consume_propagation(
                obj_id, frame_idx, reverse, report, is_cancelled, frames_processed,
                max_frames=span_frames, progress_max=total_operations)

        def _repropagate(report, is_cancelled):
            _run_span(report, is_cancelled, False, forward_frames, fwd_count)
            _run_span(report, is_cancelled, True, backward_frames, bwd_count)

        run_with_progress(progress_dialog, _repropagate)

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
    
    def _propagate_point_tracks(self):
        """Propagate point tracks through the video (SAM2++ point mode)."""
        from PyQt5.QtCore import Qt
    
        om = self.main_window.object_manager
    
        # Determine reference frame from the first tracked point across all objects
        ref_frames = {
            obj_id: min(frames.keys())
            for obj_id, frames in om.object_tracked_points.items()
            if frames
        }
        if not ref_frames:
            self.main_window.ui_manager.show_message(
                "warning",
                self.main_window.localization.get_text("warning"),
                self.main_window.localization.get_text("no_inference_state"),
            )
            return
    
        ref_frame_idx  = min(ref_frames.values())
        total_frames   = len(self.main_window.image_manager.image_paths)
    
        progress = AnimatedProgressDialog(
            self.main_window.localization.get_text("propagation_in_progress"),
            self.main_window.localization.get_text("cancel"),
            0, total_frames, self.main_window,
            configurable_pacing=True
        )
        progress.setWindowModality(Qt.WindowModal)
        # The backward pass also yields the reference frame, so progress reaches
        # the maximum one frame early; with auto-reset the dialog would then
        # hide and give the main window back while the worker still uses SAM2
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
    
        frames_done  = 0
        was_cancelled = False
    
        try:
            def _propagate(report, is_cancelled):
                nonlocal frames_done, was_cancelled

                # Forward pass
                for frame_idx, coords in self.main_window.sam2_backend.propagate_point_tracks(
                    ref_frame_idx, reverse=False
                ):
                    for obj_id, (x, y) in coords.items():
                        if obj_id not in om.object_tracked_points:
                            om.object_tracked_points[obj_id] = {}
                        om.object_tracked_points[obj_id][frame_idx] = (x, y)
                    frames_done += 1
                    report(frames_done)
                    if is_cancelled():
                        was_cancelled = True
                        break
    
                # Backward pass when reference is not the first frame
                if not was_cancelled and ref_frame_idx > 0:
                    for frame_idx, coords in self.main_window.sam2_backend.propagate_point_tracks(
                        ref_frame_idx, reverse=True
                    ):
                        for obj_id, (x, y) in coords.items():
                            if obj_id not in om.object_tracked_points:
                                om.object_tracked_points[obj_id] = {}
                            # Do not overwrite frames already filled by forward pass
                            if frame_idx not in om.object_tracked_points.get(obj_id, {}):
                                om.object_tracked_points[obj_id][frame_idx] = (x, y)
                        frames_done += 1
                        report(min(frames_done, total_frames))
                        if is_cancelled():
                            was_cancelled = True
                            break

            run_with_progress(progress, _propagate)
    
        except Exception as e:
            if self.main_window.debug_mode:
                import traceback; traceback.print_exc()
            self.main_window.ui_manager.show_message(
                "error", self.main_window.localization.get_text("error"), str(e)
            )
        finally:
            progress.close()
    
        self.main_window.display_manager.update_display()
        total_pts = sum(len(f) for f in om.object_tracked_points.values())
        msg_key   = "propagation_cancelled" if was_cancelled else "propagation_successful"
        self.main_window.ui_manager.show_message(
            "info",
            self.main_window.localization.get_text(
                "propagation_interrupted" if was_cancelled else "success"
            ),
            self.main_window.localization.get_text(
                msg_key, total_pts, len(ref_frames)
            ),
        )