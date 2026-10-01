"""
SAM2 Backend, with MedSAM2 and SAM2++ support
Handles SAM2/MedSAM2/SAM2++ model initialization, inference, and video processing
with filename management
"""

import os
import sys
import torch
import numpy as np
import shutil
import tempfile
import re
from collections import OrderedDict
from pathlib import Path
from .filename_manager import FilenameManager


class LazyVideoFrameLoader:
    """
    On-demand video frame loader with bounded LRU cache.

    Drop-in replacement for SAM2's AsyncVideoFrameLoader: instead of
    pre-allocating a single tensor for the entire sequence upfront,
    frames are loaded from disk only when first accessed and kept in a
    fixed-size LRU cache.  Memory footprint is O(cache_size) regardless
    of sequence length, making 8 000+ frame sequences practical.

    API is identical to AsyncVideoFrameLoader so it can be installed via
    a temporary monkeypatch of sam2.utils.misc.AsyncVideoFrameLoader.

    cache_size <= 0 disables eviction (unbounded cache).
    """

    def __init__(
            self,
            img_paths,
            image_size,
            offload_video_to_cpu,
            img_mean,
            img_std,
            compute_device,
            cache_size=32,
        ):
            self.img_paths            = img_paths
            self.image_size           = image_size
            self.offload_video_to_cpu = offload_video_to_cpu
            self.compute_device       = compute_device
            self.exception            = None
            self.video_height         = None
            self.video_width          = None
            self._cache               = OrderedDict()
            self._cache_size          = cache_size

            if not isinstance(img_mean, torch.Tensor):
                img_mean = torch.tensor(img_mean, dtype=torch.float32)
            if not isinstance(img_std, torch.Tensor):
                img_std = torch.tensor(img_std, dtype=torch.float32)
            self.img_mean = img_mean.reshape(3, 1, 1)
            self.img_std  = img_std.reshape(3, 1, 1)

            from sam2.utils.misc import _load_img_as_tensor
            self._load_fn = _load_img_as_tensor

            self.__getitem__(0)

    def __getitem__(self, index):
            if self.exception is not None:
                raise RuntimeError("Failure in frame loading") from self.exception

            if index in self._cache:
                self._cache.move_to_end(index)
                return self._cache[index]

            img, h, w = self._load_fn(self.img_paths[index], self.image_size)
            img = img.float()
            self.video_height = h
            self.video_width  = w
            img -= self.img_mean
            img /= self.img_std
            if not self.offload_video_to_cpu:
                img = img.to(self.compute_device, non_blocking=True)

            self._cache[index] = img
            self._cache.move_to_end(index)
            if self._cache_size > 0 and len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

            return img

    def __len__(self):
        return len(self.img_paths)


class SAM2Backend:
    """Handles SAM2/MedSAM2/SAM2++ model initialization and inference"""

    def __init__(self, debug_mode=False, image_cache_size=32):
        self.debug_mode = debug_mode

        self.sam2_config = None
        self.sam2_checkpoint = None

        # Model type flags
        self.is_medsam2   = False
        self.is_sam2plus  = False
        self.sam2plus_task = 'mask'   # 'mask' | 'point'

        self.device           = None
        self.video_predictor  = None
        self.inference_state  = None

        self.image_cache_size = image_cache_size

        self.filename_manager      = FilenameManager(debug_mode=debug_mode)
        self.temp_folder           = None
        self.original_image_folder = None

        if self.debug_mode:
            print("SAM2Backend initialized with filename management")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, checkpoint_path, model_config):
        """Initialize SAM2, MedSAM2, or SAM2++ model"""
        try:
            if self.debug_mode:
                print(f"Initializing model with checkpoint: {checkpoint_path}")
                print(f"Model config: {model_config}")

            self.sam2_checkpoint = checkpoint_path
            self.sam2_config     = model_config

            self.is_medsam2  = "MedSAM2"   in (checkpoint_path or "")
            self.is_sam2plus = "SAM2-Plus"  in (checkpoint_path or "")

            if self.debug_mode:
                model_label = self._model_label()
                print(f"Model type: {model_label}")

            # Determine compute device
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                if self.debug_mode:
                    print("Using CUDA")
                torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
                if torch.cuda.get_device_properties(0).major >= 8:
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = torch.device("mps")
                if self.debug_mode:
                    print("Using MPS (Apple Silicon)")
            else:
                self.device = torch.device("cpu")
                if self.debug_mode:
                    print("Using CPU")

            # Build video predictor — each branch imports its own builder
            if self.is_sam2plus:
                try:
                    from sam2_plus.build_sam import build_sam2_video_predictor_plus
                except ImportError as e:
                    raise RuntimeError(
                        f"sam2_plus package not found. "
                        f"Install from MCG-NJU/SAM2-Plus: {e}"
                    )
                self.video_predictor = build_sam2_video_predictor_plus(
                    model_config, checkpoint_path,
                    task=self.sam2plus_task,
                    device=self.device,
                )
            elif self.is_medsam2:
                from sam2.build_sam import build_sam2_video_predictor
                hydra_overrides_extra = ["++model.non_overlap_masks=true"]
                self.video_predictor = build_sam2_video_predictor(
                    config_file=model_config,
                    ckpt_path=checkpoint_path,
                    apply_postprocessing=False,
                    hydra_overrides_extra=hydra_overrides_extra,
                    vos_optimized=False,
                    device=self.device,
                )
            else:
                from sam2.build_sam import build_sam2_video_predictor
                self.video_predictor = build_sam2_video_predictor(
                    model_config, checkpoint_path, device=self.device
                )

            if self.debug_mode:
                print(f"{self._model_label()} video predictor initialized successfully")

            return True

        except Exception as e:
            if self.debug_mode:
                print(f"Error initializing model: {e}")
                import traceback
                traceback.print_exc()
            return False

    def _model_label(self):
        """Return a short human-readable model name."""
        if self.is_sam2plus:
            return "SAM2++"
        if self.is_medsam2:
            return "MedSAM2"
        return "SAM2"

    # ------------------------------------------------------------------
    # Inference state
    # ------------------------------------------------------------------

    def init_inference_state(self, image_folder, progress_callback=None, cancelled_flag=None):
        """Initialize inference state from image folder with lazy frame loading."""
        try:
            if self.debug_mode:
                print(f"=== INITIALIZING INFERENCE STATE ===")
                print(f"Original image folder: {image_folder}")

            image_files = self._get_image_files(image_folder)
            if not image_files:
                raise Exception("No valid image files found")

            image_paths = [os.path.join(image_folder, f) for f in image_files]
            needs_preprocessing = self._check_if_preprocessing_needed(image_files)

            if needs_preprocessing and self._is_prep_cache_valid(image_folder):
                if self.debug_mode:
                    print(f"Reusing cached temp folder: {self.temp_folder}")
                self.filename_manager.initialize_mappings(image_paths, self.temp_folder)
                folder_for_sam2 = self.temp_folder

            elif needs_preprocessing:
                if self.debug_mode:
                    print("Files need preprocessing for SAM2 compatibility")

                if self.temp_folder and os.path.exists(self.temp_folder):
                    shutil.rmtree(self.temp_folder)

                self.temp_folder = tempfile.mkdtemp(prefix="sam2_")
                self._prepare_sam2_images(
                    image_paths, self.temp_folder,
                    progress_callback=progress_callback,
                    cancelled_flag=cancelled_flag,
                )

                if cancelled_flag is not None and cancelled_flag.cancelled:
                    shutil.rmtree(self.temp_folder, ignore_errors=True)
                    self.temp_folder = None
                    return False

                self.filename_manager.initialize_mappings(image_paths, self.temp_folder)
                folder_for_sam2 = self.temp_folder

            else:
                if self.debug_mode:
                    print("Files are SAM2 compatible, using original folder")
                self.filename_manager.initialize_mappings(image_paths)
                folder_for_sam2 = image_folder

            if progress_callback is not None:
                progress_callback(0, 0, "init")

            import sam2.utils.misc as _sam2_misc
            _cache_sz  = self.image_cache_size
            _orig_cls  = _sam2_misc.AsyncVideoFrameLoader
            _sam2_misc.AsyncVideoFrameLoader = (
                lambda *a, **kw: LazyVideoFrameLoader(*a, **kw, cache_size=_cache_sz)
            )
            try:
                self.inference_state = self.video_predictor.init_state(
                    video_path=folder_for_sam2,
                    async_loading_frames=True,
                )
            finally:
                _sam2_misc.AsyncVideoFrameLoader = _orig_cls

            self.original_image_folder = image_folder

            if self.debug_mode:
                print(f"{self._model_label()} inference state initialized "
                      f"(lazy, cache={_cache_sz})")
                print(f"Device: {self.inference_state.get('device', 'unknown')}")
                stats = self.filename_manager.get_statistics()
                print(f"Filename manager stats: {stats}")

            return True

        except Exception as e:
            if self.debug_mode:
                print(f"Error initializing inference state: {e}")
                import traceback
                traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # Prediction — mask mode (SAM2 / MedSAM2 / SAM2++ mask task)
    # ------------------------------------------------------------------

    def predict_mask(self, frame_idx, obj_id, points, labels, box=None):
        """Predict mask for given points and/or bounding box on specified frame.

        `box` is [x0, y0, x1, y1] in pixels of the original video resolution,
        or None. An empty point list is forwarded as None: add_new_points_or_box
        only adds a batch dimension to 2-D point arrays, so an empty array would
        break the box concatenation.
        """
        if not self.inference_state:
            raise RuntimeError("Inference state not initialized")

        try:
            with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
                if points is None or len(points) == 0:
                    points, labels = None, None
                else:
                    if not isinstance(points, np.ndarray):
                        points = np.array(points, dtype=np.float32)
                    if not isinstance(labels, np.ndarray):
                        labels = np.array(labels)

                if self.debug_mode:
                    print(f"Predicting mask for object {obj_id} on frame {frame_idx}"
                          f"{' with box' if box is not None else ''}")

                result = self.video_predictor.add_new_points_or_box(
                    inference_state=self.inference_state,
                    frame_idx=frame_idx,
                    obj_id=obj_id,
                    points=points,
                    labels=labels,
                    box=box,
                )
                # SAM2/MedSAM2: (frame_idx, obj_ids, mask_logits)
                # SAM2++ mask:  (frame_idx, obj_ids, mask_logits, box_xyxy, score_logits)
                return result[1], result[2]

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise RuntimeError(f"Error predicting mask: {e}")

    def add_mask(self, frame_idx, obj_id, mask):
        """
        Add an externally-composed binary mask as conditioning input for the
        given object on the given frame (mask-based initialization, as an
        alternative to point-based prediction via predict_mask).
        """
        if not self.inference_state:
            raise RuntimeError("Inference state not initialized")

        try:
            with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
                if not isinstance(mask, torch.Tensor):
                    mask = torch.from_numpy(np.asarray(mask))
                mask = mask.to(torch.bool)

                if self.debug_mode:
                    print(f"Adding imported mask for object {obj_id} on frame {frame_idx}")

                result = self.video_predictor.add_new_mask(
                    inference_state=self.inference_state,
                    frame_idx=frame_idx,
                    obj_id=obj_id,
                    mask=mask,
                )
                # SAM2/MedSAM2: (frame_idx, obj_ids, mask_logits)
                # SAM2++ mask:  (frame_idx, obj_ids, mask_logits, box_xyxy, score_logits)
                return result[1], result[2]

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise RuntimeError(f"Error adding mask: {e}")

    def propagate_masks(self, start_frame_idx, reverse=False, max_frame_num_to_track=None):
        """
        Propagate masks through video.

        Yields (frame_idx, out_obj_ids, out_mask_logits) for each frame.
        Handles both SAM2/MedSAM2 (3-value yield) and SAM2++ (5-value yield)
        by indexing the result tuple — extra values are silently discarded.

        max_frame_num_to_track: optional bound on propagation length in the
        given direction (None = unbounded, propagate to the end of the video).
        """
        if not self.inference_state:
            raise RuntimeError("Inference state not initialized")

        try:
            with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
                if self.debug_mode:
                    direction = "backward" if reverse else "forward"
                    print(f"Starting {direction} propagation from frame {start_frame_idx}")

                for result in self.video_predictor.propagate_in_video(
                    self.inference_state,
                    start_frame_idx=start_frame_idx,
                    max_frame_num_to_track=max_frame_num_to_track,
                    reverse=reverse,
                ):
                    # SAM2/MedSAM2: (frame_idx, obj_ids, mask_logits)
                    # SAM2++ mask:  (frame_idx, obj_ids, mask_logits, box_xyxy, score_logits)
                    yield result[0], result[1], result[2]

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise RuntimeError(f"Error during mask propagation: {e}")

    # ------------------------------------------------------------------
    # Prediction — point tracking mode (SAM2++ point task only)
    # ------------------------------------------------------------------

    def predict_point_track(self, frame_idx, obj_id, point_xy, radius=20, sigma=10):
        """
        Register an initial tracking point for SAM2++ point mode.

        Args:
            frame_idx: Reference frame index.
            obj_id:    Object identifier.
            point_xy:  (x_px, y_px) pixel coordinates of the seed point.
            radius:    Gaussian mask radius in pixels.
            sigma:     Gaussian mask sigma in pixels.

        Returns:
            (out_obj_ids, out_heatmap_logits) — heatmap logits for the reference frame.
        """
        if not self.inference_state:
            raise RuntimeError("Inference state not initialized")
        if not self.is_sam2plus:
            raise RuntimeError("predict_point_track requires SAM2++ backend")

        with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
            points = np.array([[point_xy[0], point_xy[1]]], dtype=np.float32)
            labels = np.array([1], dtype=np.int32)   # single positive point
            result = self.video_predictor.add_new_points_and_generate_gaussian_mask(
                inference_state=self.inference_state,
                frame_idx=frame_idx,
                obj_id=obj_id,
                points=points,
                labels=labels,
                radius=radius,
                sigma=sigma,
            )
        # Unpack by index in case SAM2++ returns extra values
        return result[1], result[2]

    def propagate_point_tracks(self, start_frame_idx, reverse=False):
        """
        Propagate point tracks (SAM2++ point mode only).

        Yields (frame_idx, {obj_id: (x_px, y_px)}) for each frame.
        The position is extracted as the argmax of the Gaussian heatmap logit.
        """
        if not self.inference_state:
            raise RuntimeError("Inference state not initialized")
        if not self.is_sam2plus:
            raise RuntimeError("propagate_point_tracks requires SAM2++ backend")

        try:
            with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
                if self.debug_mode:
                    direction = "backward" if reverse else "forward"
                    print(f"Starting {direction} point-track propagation "
                          f"from frame {start_frame_idx}")

                for result in self.video_predictor.propagate_in_video(
                    self.inference_state,
                    start_frame_idx=start_frame_idx,
                    reverse=reverse,
                ):
                    frame_idx    = result[0]
                    out_obj_ids  = result[1]
                    out_heatmaps = result[2]
                    coords = {}
                    for i, obj_id in enumerate(out_obj_ids):
                        if i < len(out_heatmaps):
                            coord = self._extract_point_from_heatmap(out_heatmaps[i])
                            if coord is not None:
                                coords[obj_id] = coord
                    yield frame_idx, coords

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise RuntimeError(f"Error during point-track propagation: {e}")

    def _extract_point_from_heatmap(self, heatmap_logit):
        """
        Extract (x_px, y_px) from a Gaussian heatmap logit via argmax.

        Works with both torch.Tensor and numpy array inputs.
        """
        if isinstance(heatmap_logit, torch.Tensor):
            h_np = heatmap_logit.squeeze().cpu().float().numpy()
        else:
            h_np = np.asarray(heatmap_logit).squeeze()
        if h_np.ndim > 2:
            h_np = h_np.reshape(h_np.shape[-2], h_np.shape[-1])
        if h_np.max() <= 0.0:
            return None   # no confident prediction — caller skips this frame
        flat_idx = int(np.argmax(h_np))
        y_px, x_px = np.unravel_index(flat_idx, h_np.shape)
        return int(x_px), int(y_px)

    # ------------------------------------------------------------------
    # Legacy / alternate propagation entry point
    # ------------------------------------------------------------------

    def add_points(self, frame_idx, obj_id, points, labels):
        """Add points to object with debugging"""
        try:
            if self.debug_mode:
                print(f"Adding points: frame {frame_idx}, obj {obj_id}, "
                      f"points shape: {points.shape}")

            with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
                result = self.video_predictor.add_new_points_or_box(
                    inference_state=self.inference_state,
                    frame_idx=frame_idx,
                    obj_id=obj_id,
                    points=points,
                    labels=labels,
                )
            if self.debug_mode:
                print(f"Points added successfully, output frame: {result[0]}")
            return result[0], result[1], result[2]

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise

    def propagate_in_video(self, start_frame_idx=None):
        """Propagate masks through video with progress tracking (legacy entry point)"""
        try:
            if self.debug_mode:
                print("=== STARTING MASK PROPAGATION ===")
                if start_frame_idx is not None:
                    print(f"Starting from frame: {start_frame_idx}")

            total_frames = len(self.filename_manager.frame_to_original)
            if self.debug_mode:
                print(f"Total frames to process: {total_frames}")

            video_segments = {}

            with torch.inference_mode(), torch.autocast(self.device.type, dtype=torch.bfloat16):
                for result in self.video_predictor.propagate_in_video(
                    self.inference_state, start_frame_idx=start_frame_idx
                ):
                    out_frame_idx   = result[0]
                    out_obj_ids     = result[1]
                    out_mask_logits = result[2]
                    video_segments[out_frame_idx] = {
                        out_obj_id: (out_mask_logits[i] > 0.0).cpu().numpy()
                        for i, out_obj_id in enumerate(out_obj_ids)
                    }
                    if self.debug_mode:
                        original_filename = self.filename_manager.get_original_filename(
                            out_frame_idx)
                        print(f"Processed frame {out_frame_idx} ({original_filename}): "
                              f"{len(out_obj_ids)} objects")

            if self.debug_mode:
                print(f"=== PROPAGATION COMPLETE: {len(video_segments)} frames ===")
                self._debug_inference_state_after_propagation()

            return video_segments

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise

    # ------------------------------------------------------------------
    # Mask output processing
    # ------------------------------------------------------------------

    def process_mask_output(self, mask_logits):
        """Process raw mask logits into binary mask"""
        try:
            if len(mask_logits.shape) in (3, 4):
                mask = mask_logits.squeeze().cpu().numpy()
            elif len(mask_logits.shape) == 2:
                mask = mask_logits.cpu().numpy()
            else:
                raise ValueError(f"Unexpected mask shape: {mask_logits.shape}")

            binary_mask = mask > 0.0

            if self.debug_mode:
                print(f"Processed mask shape: {binary_mask.shape}, "
                      f"active pixels: {np.sum(binary_mask)}")
            return binary_mask

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise RuntimeError(f"Error processing mask output: {e}")

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset_state(self, preserve_prep_cache=False):
        """Reset inference state and cleanup."""
        try:
            if self.debug_mode:
                print("Resetting SAM2 state")

            if self.inference_state:
                self.inference_state.clear()
                self.inference_state = None

            self.filename_manager.clear_mappings()

            if not preserve_prep_cache:
                if self.temp_folder and os.path.exists(self.temp_folder):
                    try:
                        shutil.rmtree(self.temp_folder)
                        if self.debug_mode:
                            print(f"Cleaned up temporary directory: {self.temp_folder}")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"Warning: Could not cleanup temp dir: {e}")
                self.temp_folder           = None
                self.original_image_folder = None

            if self.device and self.device.type == 'cuda':
                torch.cuda.empty_cache()

            if self.debug_mode:
                print("SAM2 state reset complete")

        except Exception as e:
            if self.debug_mode:
                print(f"Error resetting state: {e}")

    # ------------------------------------------------------------------
    # Device / model info
    # ------------------------------------------------------------------

    def get_device_info(self):
        """Get information about the current device"""
        info = {
            'device':            str(self.device),
            'device_name':       None,
            'memory_allocated':  None,
            'memory_reserved':   None,
            'model_type':        self._model_label(),
        }
        if self.device.type == 'cuda':
            info['device_name']      = torch.cuda.get_device_name(self.device)
            info['memory_allocated'] = torch.cuda.memory_allocated(self.device)
            info['memory_reserved']  = torch.cuda.memory_reserved(self.device)
        elif self.device.type == 'mps':
            info['device_name'] = "Apple Silicon GPU"
        else:
            info['device_name'] = "CPU"
        return info

    # ------------------------------------------------------------------
    # File / folder helpers
    # ------------------------------------------------------------------

    def _get_image_files(self, folder):
        """Get sorted list of image files"""
        try:
            files = [
                f for f in os.listdir(folder)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff'))
            ]

            def natural_sort_key(filename):
                return [int(text) if text.isdigit() else text.lower()
                        for text in re.split('([0-9]+)', filename)]

            files.sort(key=natural_sort_key)

            if self.debug_mode:
                print(f"Found {len(files)} image files")
                if files:
                    print(f"First file: {files[0]}, Last file: {files[-1]}")
            return files

        except Exception as e:
            if self.debug_mode:
                print(f"Error getting image files: {e}")
            return []

    def _check_if_preprocessing_needed(self, image_files):
        """Check if files need preprocessing for SAM2"""
        try:
            for filename in image_files:
                name_without_ext = os.path.splitext(filename)[0]
                if not name_without_ext.isdigit():
                    return True
                if len(name_without_ext) > 10:
                    return True
            return False
        except Exception:
            return True

    def _is_prep_cache_valid(self, folder):
        """Return True if the preprocessed temp folder can be reused."""
        return (
            self.original_image_folder is not None
            and self.original_image_folder == folder
            and self.temp_folder is not None
            and os.path.isdir(self.temp_folder)
        )

    def _prepare_sam2_images(self, image_paths, temp_dir,
                             progress_callback=None, cancelled_flag=None):
        """Prepare images for SAM2 with temporary naming."""
        try:
            if self.debug_mode:
                print(f"Preparing {len(image_paths)} images for SAM2")

            from PIL import Image
            n = len(image_paths)

            for frame_idx, image_path in enumerate(image_paths):
                if cancelled_flag is not None and cancelled_flag.cancelled:
                    raise InterruptedError("Image preparation cancelled by user")

                temp_path = os.path.join(temp_dir, f"{frame_idx:05d}.jpg")
                with Image.open(image_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(temp_path, 'JPEG', quality=95)

                if progress_callback is not None:
                    progress_callback(frame_idx + 1, n, "prepare")

                if self.debug_mode and frame_idx < 3:
                    print(f"  Prepared: {os.path.basename(image_path)} -> "
                          f"{frame_idx:05d}.jpg")

            if self.debug_mode:
                print(f"All images prepared in: {temp_dir}")

        except InterruptedError:
            raise
        except Exception as e:
            if self.debug_mode:
                print(f"Error preparing SAM2 images: {e}")
            raise

    # ------------------------------------------------------------------
    # Filename management helpers
    # ------------------------------------------------------------------

    def get_original_filename(self, frame_index):
        return self.filename_manager.get_original_filename(frame_index)

    def get_frame_index(self, original_filename):
        return self.filename_manager.get_frame_index(original_filename)

    def get_export_filename_mapping(self, export_type="mask"):
        return self.filename_manager.get_export_filename_mapping(export_type)

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def _debug_inference_state_after_propagation(self):
        if not self.debug_mode:
            return
        try:
            print("=== DEBUGGING INFERENCE STATE AFTER PROPAGATION ===")
            main_keys = list(self.inference_state.keys())
            print(f"Main inference state keys: {main_keys}")
            if 'output_dict_per_obj' in self.inference_state:
                output_dict = self.inference_state['output_dict_per_obj']
                print(f"output_dict_per_obj objects: {list(output_dict.keys())}")
                for obj_idx, obj_data in output_dict.items():
                    print(f"  Object {obj_idx} keys: {list(obj_data.keys())}")
                    for ot in ['cond_frame_outputs', 'non_cond_frame_outputs']:
                        if ot in obj_data:
                            frames = list(obj_data[ot].keys())
                            print(f"    {ot} frames: {frames[:10]}...")
            print("=== END INFERENCE STATE DEBUG ===")
        except Exception as e:
            print(f"Error debugging inference state: {e}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        try:
            if self.inference_state is not None:
                self.reset_state()
            if self.debug_mode:
                print("SAM2 backend cleanup completed")
        except Exception:
            pass

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
