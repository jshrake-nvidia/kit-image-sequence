# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#
__all__ = ["KitImageSequenceWindow"]

import os
from glob import glob

import carb
import omni.ui
from pxr import Usd

from .config import *
from .core import *


class KitImageSequenceWindow(omni.ui.Window):
    """
    Extension window
    """

    def __init__(self, title: str, delegate=None, **kwargs):

        super().__init__(title, **kwargs)

        # Set the function that is called to build widgets when the window is
        # visible
        self._asset_path_model = omni.ui.SimpleStringModel("")
        self._ppi_model = omni.ui.SimpleIntModel(100)
        self._gap_model = omni.ui.SimpleFloatModel(0.1)
        self._curve_model = omni.ui.SimpleFloatModel(0.0)
        self._images_per_row_model = omni.ui.SimpleIntModel(1)
        self._image_sequence_is_selected = omni.ui.SimpleBoolModel(False)

        self._asset_path_model.add_end_edit_fn(lambda _: self._on_asset_path_change())
        self._ppi_model.add_value_changed_fn(lambda _: self._on_change())
        self._gap_model.add_value_changed_fn(lambda _: self._on_change())
        self._curve_model.add_value_changed_fn(lambda _: self._on_change())
        self._images_per_row_model.add_value_changed_fn(lambda _: self._on_change())
        self._image_sequence_is_selected.add_value_changed_fn(lambda _: self._on_image_seq_selection_change())

        self.frame.set_build_fn(self._build_fn)

        stage_event_stream = omni.usd.get_context().get_stage_event_stream()
        self._stage_event_sub = stage_event_stream.create_subscription_to_pop(self._on_stage_event, name="kit-imageseq-event-stream")

    def destroy(self):
        super().destroy()
        self._stage_event_sub.unsubscribe()

    def _on_stage_event(self, event):
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        SELECTION_CHANGED = int(omni.usd.StageEventType.SELECTION_CHANGED)
        if event.type == SELECTION_CHANGED:
            self._image_sequence_is_selected.set_value(False)
            selection: omni.usd.Selection = omni.usd.get_context().get_selection()
            paths = selection.get_selected_prim_paths()
            if len(paths) == 0:
                return
            first_path = paths[0]
            first_prim: Usd.Prim = stage.GetPrimAtPath(first_path)
            if not first_prim.IsValid():
                return
            # Populate the UI Model with the config values
            config = get_config_metadata(first_prim)
            if config is None:
                return
            self._selected_prim_path = first_path
            self._set_models_from_config(config)

    def _config_from_models(self) -> Config:
        config = Config()
        config.path_glob = self._asset_path_model.get_value_as_string()
        config.expanded_glob = glob(config.path_glob)
        config.expanded_glob.sort()
        config.ppi = self._ppi_model.get_value_as_int()
        config.gap_pct = self._gap_model.get_value_as_float()
        config.curve_pct = self._curve_model.get_value_as_float()
        config.images_per_row = self._images_per_row_model.get_value_as_int()
        return config

    def _set_models_from_config(self, config: Config) -> None:
        self._asset_path_model.set_value(config.path_glob)
        self._ppi_model.set_value(config.ppi)
        self._gap_model.set_value(config.gap_pct)
        self._curve_model.set_value(config.curve_pct)
        self._images_per_row_model.set_min(0)
        self._images_per_row_model.set_max(len(config.expanded_glob))
        self._images_per_row_model.set_value(config.images_per_row)
        self._image_sequence_is_selected.set_value(True)

    def _on_image_seq_selection_change(self) -> None:
        self._frame.visible = self._image_sequence_is_selected.get_value_as_bool()

    def _on_create_new_image_sequence(self) -> None:
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        # 
        root_prim: Usd.Prim = stage.GetDefaultPrim()  
        root_prim_path: Sdf.Path = root_prim.GetPath()
        root_image_seq_prim_path = root_prim_path.AppendChild("ImageSequences")
        image_seq_count = 0
        root_image_seq_prim: Usd.Prim = stage.GetPrimAtPath(root_image_seq_prim_path)
        if root_image_seq_prim.IsValid():
            image_seq_count = len(root_image_seq_prim.GetChildren())
        while True:
            image_seq_prim_path = root_image_seq_prim_path.AppendChild(f"ImageSequence{image_seq_count}")
            if not stage.GetPrimAtPath(image_seq_prim_path).IsValid():
                break
            else:
                image_seq_count += 1
            
        # Default config
        config = Config()
        config.path_glob = ""
        config.expanded_glob = []
        config.ppi = 300
        config.gap_pct = 0.0
        config.curve_pct = 0.0
        config.images_per_row = 0
        prim = create_image_sequence_group_prim(stage, image_seq_prim_path, config)
        # Select the created prim
        selected_prim_path = str(prim.GetPath())
        selection: omni.usd.Selection = omni.usd.get_context().get_selection()
        selection.set_selected_prim_paths([selected_prim_path], True)
        self._selected_prim_path = selected_prim_path
        return

    def _on_asset_path_change(self) -> None:
        # Validate user input
        config = self._config_from_models()
        if len(config.expanded_glob) == 0:
            carb.log_error(f"No assets found for {config.path_glob}")
        for asset_path in config.expanded_glob:
            if not os.path.exists(asset_path):
                carb.log_error(f"Specified asset {asset_path} does not exist")
                return
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        prim_path = Sdf.Path(self._selected_prim_path)
        prim: Usd.Prim = stage.GetPrimAtPath(prim_path)
        if prim.IsValid():
            children = prim.GetChildren()
            for child in children:
                child: Usd.Prim
                stage.RemovePrim(child.GetPath())
        prim: Usd.Prim = create_image_sequence_group_prim(stage, prim_path, config)
        selection: omni.usd.Selection = omni.usd.get_context().get_selection()
        selection.set_selected_prim_paths([str(prim.GetPath())], True)
        self._set_models_from_config(config)
        return

    def _on_change(self):
        selected_prim_path = self._selected_prim_path
        config = self._config_from_models()
        stage = omni.usd.get_context().get_stage()
        update_image_sequence_prims(stage, Sdf.Path(selected_prim_path), config)

    def _build_fn(self):
        with omni.ui.VStack():
            with omni.ui.VStack(height=20):
                with omni.ui.HStack():
                    omni.ui.Button("Create New Image Sequence", width=40, clicked_fn=self._on_create_new_image_sequence)
            self._frame = omni.ui.Frame(visible=self._image_sequence_is_selected.get_value_as_bool())
            with self._frame:
                with omni.ui.VStack(height=20):
                    with omni.ui.HStack():
                        omni.ui.Label(
                            "Asset Path", tooltip="Absolute path to an image asset or a glob like C:\dir\*.png"
                        )
                        omni.ui.StringField(self._asset_path_model)
                    omni.ui.Spacer(height=2)
                    with omni.ui.HStack():
                        omni.ui.Label("PPI", tooltip="Desired pixels per inch")
                        omni.ui.IntField(self._ppi_model)
                    omni.ui.Spacer(height=2)
                    with omni.ui.HStack():
                        omni.ui.Label("Gap", tooltip="In units of percentage of the max image width")
                        omni.ui.FloatSlider(self._gap_model, min=0.0, max=1.0)
                    omni.ui.Spacer(height=2)
                    with omni.ui.HStack():
                        omni.ui.Label("Curve", tooltip="0.0 -> straight line, 1.0 -> circle")
                        omni.ui.FloatSlider(self._curve_model, min=0.0, max=1.0)
                    omni.ui.Spacer(height=2)
                    with omni.ui.HStack():
                        omni.ui.Label("Images Per Row", tooltip="Images per row")
                        omni.ui.IntSlider(self._images_per_row_model, min=1)
                    omni.ui.Spacer(height=2)