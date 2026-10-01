"""
SAM2 Display Updater
Handles display updates after mask synchronization, refreshing all frames and providing debug output
"""

import numpy as np

class SAM2DisplayUpdater:
    """Handles display updates and notifications with enhanced debugging and fixes"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
    
    def force_display_update(self):
        """Force display update after mask synchronization with comprehensive fixes"""
        if self.debug_mode:
            print("=== FORCING DISPLAY UPDATE (ENHANCED) ===")
        
        try:
            current_frame = self.main_window.image_manager.current_image_idx
            
            if self.debug_mode:
                print(f"Current frame index: {current_frame}")
                self._debug_display_state()
            
            # CRITICAL FIX 0: Navigate to frame with masks if current frame has none
            target_frame = self._find_and_navigate_to_mask_frame()
            
            # CRITICAL FIX 1: CORRECTION MAJEURE - Resize masks to match image dimensions FOR ALL FRAMES
            self._fix_mask_dimensions_all_frames()
            
            # CRITICAL FIX 2: Force image reload to trigger proper display chain
            self._force_image_reload()
            
            # CRITICAL FIX 3: Deep debug of display_masks method
            self._debug_display_masks_method()
            
            # Update UI components
            self._update_ui_components()
            
            # CRITICAL FIX 4: Reset and restore zoom to force complete refresh
            self._reset_and_restore_zoom()
            
            # CRITICAL FIX 5: Enhanced display manager update with validation
            self._update_display_manager_enhanced()
            
            # CRITICAL FIX 6: Force canvas refresh with Qt event processing
            self._refresh_canvas_enhanced()
            
            # CRITICAL FIX 7: Verify and force final display if needed
            self._verify_and_force_final_display()
            
            # CRITICAL FIX 8: Final validation and correction if still no display
            self._final_display_validation_and_fix()
            
            if self.debug_mode:
                self._debug_display_state()
                print("=== DISPLAY UPDATE COMPLETE (ENHANCED) ===")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error updating display: {e}")
                import traceback
                traceback.print_exc()
    
    def _find_and_navigate_to_mask_frame(self):
        """CRITICAL FIX: Navigate to a frame that contains masks after import"""
        try:
            current_frame = self.main_window.image_manager.current_image_idx
            
            # Check if current frame has any masks
            current_frame_has_masks = False
            for obj_id, masks in self.main_window.object_manager.object_masks.items():
                if current_frame in masks:
                    current_frame_has_masks = True
                    break
            
            if current_frame_has_masks:
                if self.debug_mode:
                    print(f"NAVIGATION: Current frame {current_frame} has masks, staying")
                return current_frame
            
            # Find frames with masks
            frames_with_masks = set()
            for obj_id, masks in self.main_window.object_manager.object_masks.items():
                frames_with_masks.update(masks.keys())
            
            if not frames_with_masks:
                if self.debug_mode:
                    print("NAVIGATION: No frames with masks found")
                return current_frame
            
            # Choose best frame to navigate to (closest to current, or first available)
            sorted_frames = sorted(frames_with_masks)
            
            # Find closest frame to current
            best_frame = min(sorted_frames, key=lambda f: abs(f - current_frame))
            
            if self.debug_mode:
                print(f"NAVIGATION: Current frame {current_frame} has no masks")
                print(f"NAVIGATION: Available frames with masks: {sorted_frames}")
                print(f"NAVIGATION: Navigating to frame {best_frame}")
            
            # Navigate to the frame with masks
            self.main_window.image_manager.load_image(best_frame)
            
            # Update navigation UI
            if hasattr(self.main_window, 'ui_manager'):
                total_images = len(self.main_window.image_manager.image_paths)
                self.main_window.ui_manager.update_navigation_controls(best_frame, total_images)
            
            return best_frame
            
        except Exception as e:
            if self.debug_mode:
                print(f"NAVIGATION ERROR: {e}")
            return current_frame
    
    def _fix_mask_dimensions_all_frames(self):
        """CORRECTION MAJEURE: Resize imported masks to match image dimensions FOR ALL FRAMES"""
        try:
            if self.debug_mode:
                print("MASK RESIZE ALL FRAMES: Starting comprehensive dimension correction")
            
            # Get current image dimensions (all images should have same dimensions)
            if not self.main_window.image_manager.has_images():
                if self.debug_mode:
                    print("MASK RESIZE ALL FRAMES: No images available")
                return
            
            current_image = self.main_window.image_manager.get_current_image()
            if current_image is None:
                if self.debug_mode:
                    print("MASK RESIZE ALL FRAMES: Current image is None")
                return
            
            target_h, target_w = current_image.shape[:2]
            
            if self.debug_mode:
                print(f"MASK RESIZE ALL FRAMES: Target image dimensions: {target_h}x{target_w}")
            
            total_masks_resized = 0
            
            # Process ALL frames, not just the current one
            for obj_id in list(self.main_window.object_manager.object_masks.keys()):
                obj_masks = self.main_window.object_manager.object_masks[obj_id]
                
                if self.debug_mode:
                    print(f"MASK RESIZE ALL FRAMES: Processing object {obj_id} with {len(obj_masks)} frames")
                
                # Process each frame for this object
                for frame_idx in list(obj_masks.keys()):
                    mask = obj_masks[frame_idx]
                    mask_h, mask_w = mask.shape[:2]
                    
                    if self.debug_mode:
                        print(f"MASK RESIZE ALL FRAMES: Object {obj_id}, Frame {frame_idx}: {mask_h}x{mask_w}")
                    
                    # Check whether resizing is needed
                    if mask_h != target_h or mask_w != target_w:
                        if self.debug_mode:
                            print(f"MASK RESIZE ALL FRAMES: Resizing object {obj_id} frame {frame_idx} from {mask_h}x{mask_w} to {target_h}x{target_w}")

                        # Resize the mask
                        resized_mask = self._resize_mask(mask, target_h, target_w)

                        # Update the mask in Object Manager
                        self.main_window.object_manager.object_masks[obj_id][frame_idx] = resized_mask

                        # Recalculate the centroid for the resized mask
                        centroid = self.main_window.object_manager.calculate_centroid(resized_mask)
                        if centroid:
                            if obj_id not in self.main_window.object_manager.object_centroids:
                                self.main_window.object_manager.object_centroids[obj_id] = {}
                            self.main_window.object_manager.object_centroids[obj_id][frame_idx] = centroid
                            
                            if self.debug_mode:
                                print(f"MASK RESIZE ALL FRAMES: Updated centroid for object {obj_id} frame {frame_idx}: {centroid}")
                        
                        total_masks_resized += 1
                        
                        if self.debug_mode:
                            active_pixels_before = np.sum(mask)
                            active_pixels_after = np.sum(resized_mask)
                            print(f"MASK RESIZE ALL FRAMES: Object {obj_id} frame {frame_idx} - pixels before: {active_pixels_before}, after: {active_pixels_after}")
                    else:
                        if self.debug_mode:
                            print(f"MASK RESIZE ALL FRAMES: Object {obj_id} frame {frame_idx} already correct size")
            
            if self.debug_mode:
                print(f"MASK RESIZE ALL FRAMES: COMPLETE - Resized {total_masks_resized} masks across all frames")
                
        except Exception as e:
            if self.debug_mode:
                print(f"MASK RESIZE ALL FRAMES ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    def _fix_mask_dimensions(self):
        """LEGACY METHOD: Resize imported masks to match current image dimensions (current frame only)"""
        try:
            if self.debug_mode:
                print("MASK RESIZE: Starting dimension correction (current frame only)")
            
            # Get current image dimensions
            if not self.main_window.image_manager.has_images():
                if self.debug_mode:
                    print("MASK RESIZE: No images available")
                return
            
            current_image = self.main_window.image_manager.get_current_image()
            if current_image is None:
                if self.debug_mode:
                    print("MASK RESIZE: Current image is None")
                return
            
            target_h, target_w = current_image.shape[:2]
            current_frame = self.main_window.image_manager.current_image_idx
            
            if self.debug_mode:
                print(f"MASK RESIZE: Target image dimensions: {target_h}x{target_w}")
                print(f"MASK RESIZE: Current frame: {current_frame}")
            
            masks_resized = 0
            
            # Check and resize all masks for current frame
            for obj_id in list(self.main_window.object_manager.object_masks.keys()):
                obj_masks = self.main_window.object_manager.object_masks[obj_id]
                
                if current_frame not in obj_masks:
                    if self.debug_mode:
                        print(f"MASK RESIZE: Object {obj_id} has no mask on frame {current_frame}")
                    continue
                
                mask = obj_masks[current_frame]
                mask_h, mask_w = mask.shape[:2]
                
                if self.debug_mode:
                    print(f"MASK RESIZE: Object {obj_id} mask: {mask_h}x{mask_w}")
                
                # Check if resize is needed
                if mask_h != target_h or mask_w != target_w:
                    if self.debug_mode:
                        print(f"MASK RESIZE: Resizing object {obj_id} mask from {mask_h}x{mask_w} to {target_h}x{target_w}")
                    
                    # Resize mask using best available method
                    resized_mask = self._resize_mask(mask, target_h, target_w)
                    
                    # Update the mask in Object Manager
                    self.main_window.object_manager.object_masks[obj_id][current_frame] = resized_mask
                    
                    # Recalculate centroid for resized mask
                    centroid = self.main_window.object_manager.calculate_centroid(resized_mask)
                    if centroid:
                        if obj_id not in self.main_window.object_manager.object_centroids:
                            self.main_window.object_manager.object_centroids[obj_id] = {}
                        self.main_window.object_manager.object_centroids[obj_id][current_frame] = centroid
                        if self.debug_mode:
                            print(f"MASK RESIZE: Updated centroid for object {obj_id}: {centroid}")
                    
                    masks_resized += 1
                    
                    if self.debug_mode:
                        active_pixels_before = np.sum(mask)
                        active_pixels_after = np.sum(resized_mask)
                        print(f"MASK RESIZE: Object {obj_id} - pixels before: {active_pixels_before}, after: {active_pixels_after}")
                else:
                    if self.debug_mode:
                        print(f"MASK RESIZE: Object {obj_id} mask already correct size")
            
            if self.debug_mode:
                print(f"MASK RESIZE: Resized {masks_resized} masks")
                
        except Exception as e:
            if self.debug_mode:
                print(f"MASK RESIZE ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    def _resize_mask(self, mask, target_h, target_w):
        """Resize mask to target dimensions using appropriate interpolation"""
        try:
            import cv2
            
            # Convert boolean mask to uint8 for OpenCV
            if mask.dtype == bool:
                mask_uint8 = mask.astype(np.uint8) * 255
            else:
                mask_uint8 = (mask * 255).astype(np.uint8)
            
            # Resize using nearest neighbor to preserve binary nature
            resized_mask_uint8 = cv2.resize(mask_uint8, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            
            # Convert back to boolean
            resized_mask = (resized_mask_uint8 > 127).astype(bool)
            
            if self.debug_mode:
                print("MASK RESIZE: Using OpenCV")
            
            return resized_mask
            
        except ImportError:
            # Fallback without OpenCV using scipy
            if self.debug_mode:
                print("MASK RESIZE: OpenCV not available, using scipy fallback")
            return self._resize_mask_scipy(mask, target_h, target_w)
        except Exception as e:
            if self.debug_mode:
                print(f"MASK RESIZE: OpenCV resize failed: {e}, using scipy fallback")
            return self._resize_mask_scipy(mask, target_h, target_w)
    
    def _resize_mask_scipy(self, mask, target_h, target_w):
        """Fallback mask resize using scipy"""
        try:
            from scipy.ndimage import zoom
            
            # Calculate zoom factors
            zoom_h = target_h / mask.shape[0]
            zoom_w = target_w / mask.shape[1]
            
            # Resize using nearest neighbor
            resized_mask = zoom(mask.astype(float), (zoom_h, zoom_w), order=0)
            
            # Convert back to boolean
            resized_mask = (resized_mask > 0.5).astype(bool)
            
            if self.debug_mode:
                print("MASK RESIZE: Using SciPy zoom()")
            
            return resized_mask
            
        except ImportError:
            if self.debug_mode:
                print("MASK RESIZE: scipy not available, using numpy fallback")
            return self._resize_mask_numpy(mask, target_h, target_w)
        except Exception as e:
            if self.debug_mode:
                print(f"MASK RESIZE: scipy resize failed: {e}, using numpy fallback")
            return self._resize_mask_numpy(mask, target_h, target_w)
    
    def _resize_mask_numpy(self, mask, target_h, target_w):
        """Simple numpy-based mask resize (basic but functional)"""
        try:
            # Simple nearest neighbor resize using numpy indexing
            h_indices = np.round(np.linspace(0, mask.shape[0] - 1, target_h)).astype(int)
            w_indices = np.round(np.linspace(0, mask.shape[1] - 1, target_w)).astype(int)
            
            # Create meshgrid and index
            h_grid, w_grid = np.meshgrid(h_indices, w_indices, indexing='ij')
            resized_mask = mask[h_grid, w_grid]
            
            if self.debug_mode:
                print("MASK RESIZE: Using NumPy fallback")
            
            return resized_mask.astype(bool)
            
        except Exception as e:
            if self.debug_mode:
                print(f"MASK RESIZE: numpy resize failed: {e}")
            # Return original mask as last resort
            return mask
    
    def _force_image_reload(self):
        """CRITICAL FIX: Force reload of current image to trigger display chain"""
        try:
            current_idx = self.main_window.image_manager.current_image_idx
            if self.debug_mode:
                print(f"FORCE RELOAD: Reloading image {current_idx}")
            
            # Store current image path for verification
            current_path = self.main_window.image_manager.get_current_image_path()
            
            # Force reload via ImageManager - this should trigger display update
            self.main_window.image_manager.load_image(current_idx)
            
            # Verify reload occurred
            if self.debug_mode:
                new_path = self.main_window.image_manager.get_current_image_path()
                print(f"FORCE RELOAD: Path verification - {current_path == new_path}")
            
        except Exception as e:
            if self.debug_mode:
                print(f"FORCE RELOAD ERROR: {e}")
    
    def _debug_display_masks_method(self):
        """CRITICAL DEBUG: Deep dive into display_masks method behavior"""
        if not self.debug_mode:
            return
        
        try:
            print("=== DEEP DEBUG: DISPLAY_MASKS METHOD ===")
            
            # Check if display_manager exists and has proper access
            if not hasattr(self.main_window, 'display_manager'):
                print("CRITICAL ERROR: No display_manager found!")
                return
            
            dm = self.main_window.display_manager
            
            # Check UI manager connection
            if not hasattr(dm, 'ui_manager'):
                print("CRITICAL ERROR: display_manager has no ui_manager!")
                return
            
            # Check current image
            if not self.main_window.image_manager.has_images():
                print("CRITICAL ERROR: No images loaded!")
                return
            
            current_image = self.main_window.image_manager.get_current_image()
            if current_image is None:
                print("CRITICAL ERROR: Current image is None!")
                return
            
            h, w = current_image.shape[:2]
            print(f"Image dimensions: {h}x{w}")
            
            # Check object masks directly
            current_frame = self.main_window.image_manager.current_image_idx
            object_masks = self.main_window.object_manager.object_masks
            
            print(f"Current frame: {current_frame}")
            print(f"Available objects: {list(object_masks.keys())}")
            
            masks_found = 0
            for obj_id in sorted(object_masks.keys()):
                obj_masks = object_masks[obj_id]
                print(f"Object {obj_id} frames: {list(obj_masks.keys())}")
                
                if current_frame in obj_masks:
                    mask = obj_masks[current_frame]
                    print(f"Object {obj_id} mask: shape={mask.shape}, dtype={mask.dtype}, active={np.sum(mask)}")
                    
                    # Check mask processing in display_masks logic
                    self._test_mask_processing(obj_id, mask, h, w)
                    masks_found += 1
            
            print(f"Total masks found on current frame: {masks_found}")
            print("=== END DEEP DEBUG: DISPLAY_MASKS METHOD ===")
            
        except Exception as e:
            print(f"DEEP DEBUG ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    def _test_mask_processing(self, obj_id, mask, target_h, target_w):
        """Test the mask processing logic that happens in display_masks"""
        try:
            print(f"  TESTING MASK PROCESSING for object {obj_id}")
            
            # Get mask color
            mask_color = self.main_window.object_manager.object_colors[obj_id]['mask']
            print(f"  Mask color: R={mask_color.red()}, G={mask_color.green()}, B={mask_color.blue()}, A={mask_color.alpha()}")
            
            # Test mask shape normalization (from display_masks logic)
            processed_mask = mask
            if len(mask.shape) > 2:
                if len(mask.shape) == 4:  # (1, 1, H, W)
                    processed_mask = mask[0, 0]
                elif len(mask.shape) == 3:  # (1, H, W) or (H, W, 1)
                    if mask.shape[0] == 1:
                        processed_mask = mask[0]
                    elif mask.shape[2] == 1:
                        processed_mask = mask[:, :, 0]
                    else:
                        processed_mask = mask[0]
            
            print(f"  Processed mask shape: {processed_mask.shape}")
            print(f"  Target image size: {target_h}x{target_w}")
            
            # Check if shapes match (critical for display)
            shapes_match = processed_mask.shape[:2] == (target_h, target_w)
            print(f"  Shapes match: {shapes_match}")
            
            if not shapes_match:
                print(f"  WARNING: Mask shape {processed_mask.shape[:2]} != image shape ({target_h}, {target_w})")
                print(f"  This will cause the mask to NOT display!")
            else:
                print(f"  SUCCESS: Mask dimensions are compatible for display")
            
            # Test mask overlay creation
            mask_color_rgb = np.array([
                mask_color.red(), 
                mask_color.green(), 
                mask_color.blue()
            ]) / 255.0
            
            print(f"  Mask color RGB: {mask_color_rgb}")
            print(f"  Mask alpha: {mask_color.alphaF()}")
            
            # Test if mask has any active pixels
            active_pixels = np.sum(processed_mask)
            print(f"  Active pixels: {active_pixels}")
            
            if active_pixels == 0:
                print(f"  WARNING: Mask has no active pixels!")
            else:
                print(f"  SUCCESS: Mask has {active_pixels} active pixels")
            
        except Exception as e:
            print(f"  MASK PROCESSING TEST ERROR: {e}")
    
    def _reset_and_restore_zoom(self):
        """CRITICAL FIX: Reset and restore zoom to force complete refresh"""
        try:
            display_mgr = self.main_window.display_manager
            
            if self.debug_mode:
                print("ZOOM RESET: Capturing current zoom state")
            
            # Capture current zoom state
            display_mgr.capture_global_zoom_state()
            saved_xlim = display_mgr.global_xlim
            saved_ylim = display_mgr.global_ylim
            
            # Reset zoom to force full refresh
            display_mgr.reset_global_zoom()
            
            if self.debug_mode:
                print("ZOOM RESET: Performing update without zoom")
            
            # Update display without zoom
            display_mgr.update_display()
            self._process_qt_events()
            
            # Restore zoom if it was set
            if saved_xlim is not None and saved_ylim is not None:
                if self.debug_mode:
                    print("ZOOM RESET: Restoring zoom state")
                display_mgr.global_xlim = saved_xlim
                display_mgr.global_ylim = saved_ylim
                display_mgr.update_display(maintain_global_zoom=True)
                self._process_qt_events()
            
            if self.debug_mode:
                print("ZOOM RESET: Complete")
                
        except Exception as e:
            if self.debug_mode:
                print(f"ZOOM RESET ERROR: {e}")
    
    def _update_display_manager_enhanced(self):
        """CRITICAL FIX: Enhanced display manager update with validation"""
        try:
            if not hasattr(self.main_window, 'display_manager'):
                if self.debug_mode:
                    print("DISPLAY UPDATE ERROR: No display_manager")
                return
            
            display_mgr = self.main_window.display_manager
            
            if self.debug_mode:
                print("DISPLAY UPDATE: Starting enhanced update sequence")
            
            # Method 1: Direct display manager calls
            for attempt in range(5):  # Increased attempts
                if self.debug_mode:
                    print(f"DISPLAY UPDATE: Attempt {attempt + 1}")
                
                # Update without zoom maintenance first
                display_mgr.update_display(maintain_global_zoom=False)
                self._process_qt_events()
                
                # Brief pause for Qt processing
                import time
                time.sleep(0.02)
            
            # Method 2: Via main window delegation (if available)
            if hasattr(self.main_window, 'update_display'):
                if self.debug_mode:
                    print("DISPLAY UPDATE: Via main window delegation")
                self.main_window.update_display(maintain_global_zoom=False)
                self._process_qt_events()
            
            # Method 3: Final update with zoom maintenance
            if self.debug_mode:
                print("DISPLAY UPDATE: Final update with zoom maintenance")
            display_mgr.update_display(maintain_global_zoom=True)
            self._process_qt_events()
            
            if self.debug_mode:
                print("DISPLAY UPDATE: Enhanced sequence complete")
                
        except Exception as e:
            if self.debug_mode:
                print(f"DISPLAY UPDATE ERROR: {e}")
    
    def _refresh_canvas_enhanced(self):
        """CRITICAL FIX: Enhanced canvas refresh with comprehensive coverage"""
        try:
            if self.debug_mode:
                print("CANVAS REFRESH: Starting enhanced refresh")
            
            # Collect all possible canvas references
            canvases_to_refresh = []
            
            # Canvas via display manager
            if (hasattr(self.main_window, 'display_manager') and 
                hasattr(self.main_window.display_manager, 'ui_manager') and 
                hasattr(self.main_window.display_manager.ui_manager, 'canvas')):
                canvases_to_refresh.append(('display_manager.ui_manager.canvas', 
                                          self.main_window.display_manager.ui_manager.canvas))
            
            # Canvas via main window
            if hasattr(self.main_window, 'canvas'):
                canvases_to_refresh.append(('main_window.canvas', self.main_window.canvas))
            
            # Canvas via ui_manager
            if (hasattr(self.main_window, 'ui_manager') and 
                hasattr(self.main_window.ui_manager, 'canvas')):
                canvases_to_refresh.append(('ui_manager.canvas', self.main_window.ui_manager.canvas))
            
            if self.debug_mode:
                print(f"CANVAS REFRESH: Found {len(canvases_to_refresh)} canvas references")
            
            # Refresh each canvas with multiple methods
            for i, (canvas_name, canvas) in enumerate(canvases_to_refresh):
                if self.debug_mode:
                    print(f"CANVAS REFRESH: Refreshing {canvas_name}")
                
                # Try multiple refresh methods
                refresh_methods = []
                if hasattr(canvas, 'draw'):
                    refresh_methods.append('draw')
                if hasattr(canvas, 'draw_idle'):
                    refresh_methods.append('draw_idle')
                if hasattr(canvas, 'flush_events'):
                    refresh_methods.append('flush_events')
                
                for method in refresh_methods:
                    try:
                        getattr(canvas, method)()
                        if self.debug_mode:
                            print(f"  Called {method}()")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"  Error calling {method}(): {e}")
                
                # Process Qt events between canvas refreshes
                self._process_qt_events()
            
            # Final comprehensive Qt event processing
            self._process_qt_events()
            
            if self.debug_mode:
                print("CANVAS REFRESH: Enhanced refresh complete")
                
        except Exception as e:
            if self.debug_mode:
                print(f"CANVAS REFRESH ERROR: {e}")
    
    def _verify_and_force_final_display(self):
        """CRITICAL FIX: Verify display success and force final update if needed"""
        try:
            current_frame = self.main_window.image_manager.current_image_idx
            masks_should_display = 0
            
            # Count masks that should be displayed
            for obj_id, masks in self.main_window.object_manager.object_masks.items():
                if current_frame in masks:
                    masks_should_display += 1
            
            if self.debug_mode:
                print(f"VERIFICATION: {masks_should_display} masks should be displayed on frame {current_frame}")
            
            if masks_should_display > 0:
                # Force a final display update sequence
                if self.debug_mode:
                    print("VERIFICATION: Forcing final display sequence")
                
                # Clear and redraw canvas
                if hasattr(self.main_window.display_manager, 'ui_manager'):
                    canvas = self.main_window.display_manager.ui_manager.canvas
                    if hasattr(canvas, 'axes'):
                        canvas.axes.clear()
                
                # Force complete redraw
                self.main_window.display_manager.update_display()
                self._process_qt_events()
                
                # Additional forced refresh
                self.main_window.display_manager.update_display(maintain_global_zoom=True)
                self._process_qt_events()
                
                if self.debug_mode:
                    print("VERIFICATION: Final display sequence complete")
            
        except Exception as e:
            if self.debug_mode:
                print(f"VERIFICATION ERROR: {e}")
    
    def _final_display_validation_and_fix(self):
        """CRITICAL FIX: Final validation and force correction if display still fails"""
        try:
            current_frame = self.main_window.image_manager.current_image_idx
            
            if self.debug_mode:
                print("FINAL VALIDATION: Checking if masks are actually displayed")
            
            # Check if we have masks that should be visible
            masks_count = 0
            for obj_id, masks in self.main_window.object_manager.object_masks.items():
                if current_frame in masks:
                    masks_count += 1
            
            if masks_count == 0:
                if self.debug_mode:
                    print("FINAL VALIDATION: No masks on current frame - this is expected")
                return
            
            # Force one more comprehensive update sequence
            if self.debug_mode:
                print(f"FINAL VALIDATION: {masks_count} masks should be visible, forcing comprehensive refresh")
            
            # Method 1: Clear and rebuild display
            try:
                if hasattr(self.main_window.display_manager, 'ui_manager'):
                    canvas = self.main_window.display_manager.ui_manager.canvas
                    if hasattr(canvas, 'axes'):
                        canvas.axes.clear()
                        canvas.axes.axis('off')
            except Exception as e:
                if self.debug_mode:
                    print(f"FINAL VALIDATION: Canvas clear error: {e}")
            
            # Method 2: Force complete display pipeline
            for final_attempt in range(3):
                if self.debug_mode:
                    print(f"FINAL VALIDATION: Comprehensive refresh attempt {final_attempt + 1}")
                
                try:
                    # Force display update
                    self.main_window.display_manager.update_display(maintain_global_zoom=False)
                    self._process_qt_events()
                    
                    # Force canvas draw
                    if hasattr(self.main_window.display_manager, 'ui_manager'):
                        canvas = self.main_window.display_manager.ui_manager.canvas
                        if hasattr(canvas, 'draw'):
                            canvas.draw()
                        if hasattr(canvas, 'flush_events'):
                            canvas.flush_events()
                    
                    self._process_qt_events()
                    
                    # Pause between attempts
                    import time
                    time.sleep(0.05)
                    
                except Exception as e:
                    if self.debug_mode:
                        print(f"FINAL VALIDATION: Attempt {final_attempt + 1} error: {e}")
            
            if self.debug_mode:
                print("FINAL VALIDATION: Comprehensive refresh complete")
        
        except Exception as e:
            if self.debug_mode:
                print(f"FINAL VALIDATION ERROR: {e}")
    
    def _process_qt_events(self):
        """Enhanced Qt event processing"""
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QCoreApplication
            
            # Multiple event processing approaches
            QApplication.processEvents()
            QCoreApplication.processEvents()
            QApplication.flush()
            
            # Additional sync for canvas events
            try:
                QApplication.sync()
            except:
                pass
            
        except Exception as e:
            if self.debug_mode:
                print(f"QT EVENTS ERROR: {e}")
    
    def _update_ui_components(self):
        """Update UI components"""
        try:
            if hasattr(self.main_window, 'ui_manager'):
                self.main_window.ui_manager.update_objects_list()
                self.main_window.ui_manager.update_object_ui()
                
                if self.debug_mode:
                    print("UI COMPONENTS: Updated objects list and UI")
        except Exception as e:
            if self.debug_mode:
                print(f"UI COMPONENTS ERROR: {e}")
    
    def _debug_display_state(self):
        """Enhanced debug of display state"""
        if not self.debug_mode:
            return
        
        print("=== DISPLAY STATE DEBUG (ENHANCED) ===")
        
        current_frame = self.main_window.image_manager.current_image_idx
        print(f"Current frame: {current_frame}")
        
        # Check Object Manager state in detail
        total_masks = 0
        current_frame_masks = 0
        for obj_id, masks in self.main_window.object_manager.object_masks.items():
            total_masks += len(masks)
            if current_frame in masks:
                current_frame_masks += 1
                mask = masks[current_frame]
                print(f"Object {obj_id}: Mask on frame {current_frame}, shape {mask.shape}, active pixels: {np.sum(mask)}")
                
                # Additional mask details
                print(f"  Mask dtype: {mask.dtype}, min: {np.min(mask)}, max: {np.max(mask)}")
                
                # Check object colors
                if obj_id in self.main_window.object_manager.object_colors:
                    mask_color = self.main_window.object_manager.object_colors[obj_id]['mask']
                    print(f"  Color: RGBA({mask_color.red()}, {mask_color.green()}, {mask_color.blue()}, {mask_color.alpha()})")
            else:
                available_frames = list(masks.keys())
                print(f"Object {obj_id}: NO mask on frame {current_frame}, available frames: {available_frames}")
        
        print(f"Total masks: {total_masks}, Current frame masks: {current_frame_masks}")
        
        # Check image state
        if self.main_window.image_manager.has_images():
            current_image = self.main_window.image_manager.get_current_image()
            if current_image is not None:
                print(f"Current image shape: {current_image.shape}")
            else:
                print("Current image is None!")
        else:
            print("No images loaded!")
        
        # Check display manager access chain
        print("=== DISPLAY MANAGER ACCESS CHAIN ===")
        has_display_mgr = hasattr(self.main_window, 'display_manager')
        print(f"main_window.display_manager exists: {has_display_mgr}")
        
        if has_display_mgr:
            dm = self.main_window.display_manager
            has_ui_mgr = hasattr(dm, 'ui_manager')
            print(f"display_manager.ui_manager exists: {has_ui_mgr}")
            
            if has_ui_mgr:
                has_canvas = hasattr(dm.ui_manager, 'canvas')
                print(f"ui_manager.canvas exists: {has_canvas}")
                
                if has_canvas and hasattr(dm.ui_manager.canvas, 'axes'):
                    print("Canvas axes access: OK")
                else:
                    print("Canvas axes access: FAILED")
            else:
                print("UI manager access: FAILED")
        
        print("=== END DISPLAY STATE DEBUG ===")