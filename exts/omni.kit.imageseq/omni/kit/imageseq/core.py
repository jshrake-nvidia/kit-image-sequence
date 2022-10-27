import math
from pathlib import Path
from typing import Dict, List

import carb
from PIL import Image
from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdShade

from .config import Config, set_config_metadata


def create_textured_quad_prim(
    stage: Usd.Stage, prim_path: Sdf.Path, translate: Gf.Vec3d, scale: Gf.Vec3d, rotate: Gf.Vec3d, image_path: str
) -> Usd.Prim:
    prim: UsdGeom.Xform = UsdGeom.Xform.Define(stage, prim_path)
    Usd.ModelAPI(prim).SetKind(Kind.Tokens.subcomponent)
    translate_op: UsdGeom.XformOp = prim.AddTranslateOp()
    rotate_op: UsdGeom.XformOp = prim.AddRotateXYZOp()
    scale_op: UsdGeom.XformOp = prim.AddScaleOp()
    translate_op.Set(translate)
    rotate_op.Set(rotate)
    scale_op.Set(Gf.Vec3d(1, 1, 1))
    mesh = create_quad_mesh(stage, scale, prim_path.AppendChild("ImageSequenceMesh"))
    material = create_texture_material(stage, prim_path.AppendChild("ImageSequenceMaterial"), image_path)
    UsdShade.MaterialBindingAPI(mesh).Bind(material)
    return prim


def create_quad_mesh(stage: Usd.Stage, scale: Gf.Vec3d, prim_path: Sdf.Path) -> UsdGeom.Mesh:
    # See https://graphics.pixar.com/usd/dev/tut_simple_shading.html#adding-a-mesh-billboard
    mesh: UsdGeom.Mesh = UsdGeom.Mesh.Define(stage, prim_path)
    translate_op: UsdGeom.XformOp = mesh.AddTranslateOp()
    rotate_op: UsdGeom.XformOp = mesh.AddRotateXYZOp()
    scale_op: UsdGeom.XformOp = mesh.AddScaleOp()
    translate_op.Set(Gf.Vec3d(0, 0, 0))
    rotate_op.Set(Gf.Vec3d(0, 0, 0))
    scale_op.Set(scale)
    mesh.CreatePointsAttr([(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)])
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateExtentAttr([(-0.5, 0.0, -0.5), (0.5, 0.0, 0.5)])
    texCoords = mesh.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying)
    texCoords.Set([(0, 0), (1, 0), (1, 1), (0, 1)])
    return mesh


def create_texture_material(stage: Usd.Stage, material_prim_path: Sdf.Path, image_path: str) -> UsdShade.Material:
    # See https://graphics.pixar.com/usd/dev/tut_simple_shading.html#adding-a-mesh-billboard
    shader_prim_path = material_prim_path.AppendChild("ImageSequenceShader")
    material: UsdShade.Material = UsdShade.Material.Define(stage, material_prim_path)
    shader: UsdShade.Shader = UsdShade.Shader.Define(stage, shader_prim_path)
    shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    shader.SetSourceAsset("OmniPBR.mdl", "mdl")
    shader.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    material.CreateSurfaceOutput("mdl").ConnectToSource(shader.ConnectableAPI(), "out")
    shader_prim: Usd.Prim = stage.GetPrimAtPath(shader_prim_path)
    shader_prim.CreateAttribute("inputs:diffuse_texture", Sdf.ValueTypeNames.Asset).Set(image_path)
    shader_prim.CreateAttribute("inputs:emissive_color_texture", Sdf.ValueTypeNames.Asset).Set(image_path)
    shader_prim.CreateAttribute("inputs:reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(1.0)
    shader_prim.CreateAttribute("inputs:metallic_constant", Sdf.ValueTypeNames.Float).Set(0.0)
    return material

class Transform:
    translate: Gf.Vec2d = Gf.Vec3d(0, 0, 0)
    scale: Gf.Vec2d = Gf.Vec3d(1, 1, 1)
    rotate: Gf.Vec2d = Gf.Vec3d(0, 0, 0)

def calculate_transforms(config: Config) -> Dict[str, Transform]:
    INCHES_TO_CM = 1.54
    images: List[Image.Image] = [Image.open(image_path_str) for image_path_str in config.expanded_glob]
    image_count = len(images)
    if image_count == 0:
        return {}
    # Calculate the largest image width in cm
    max_image_width_px = max([image.size[0] for image in images])
    max_image_width_in = max_image_width_px / config.ppi
    max_image_width_cm = max_image_width_in * INCHES_TO_CM

    # Calculate the largest image height in cm
    max_image_height_px = max([image.size[1] for image in images])
    max_image_height_in = max_image_height_px / config.ppi
    max_image_height_cm = max_image_height_in * INCHES_TO_CM

    # Calculate the number of images per row
    images_per_row = image_count if config.images_per_row < 1 else config.images_per_row
    # Calculate the total number of rows
    total_rows = math.ceil(image_count / images_per_row)
    #print(f"Images per row: {images_per_row}, Total Rows: {total_rows}")

    image_gap_cm = config.gap_pct * max_image_width_cm

    # Calculate total extents
    total_width_cm = max(max_image_width_cm * (images_per_row - 1) + image_gap_cm * max(images_per_row - 1, 0), 0)
    total_height_cm = (total_rows - 1) * max_image_height_cm + image_gap_cm * max(total_rows - 1, 0)
    #print(f"Total Width: {total_width_cm}, Total Height: {total_height_cm}")

    # max_height_px = max([image.size[1] for image in images])
    left_most_cm = -0.5 * total_width_cm
    top_most_cm = 0.5 * total_height_cm

    left_current_cm = left_most_cm
    top_current_cm = top_most_cm
    transforms: Dict[str, Transform] = {}

    seen = 0
    for count, image in enumerate(images):
        if seen > images_per_row - 1:
            left_current_cm = left_most_cm
            top_current_cm -= max_image_height_cm + image_gap_cm
            seen = 0
        image_width_px = image.size[0]
        image_height_px = image.size[1]
        image_width_in = image_width_px / config.ppi
        image_height_in = image_height_px / config.ppi
        image_width_cm = image_width_in * INCHES_TO_CM
        image_height_cm = image_height_in * INCHES_TO_CM
        transform = Transform()
        transform.scale = Gf.Vec3d(image_width_cm, image_height_cm, 1)

        # Lerp between the line and the arc positioning
        t = (left_current_cm - left_most_cm) / total_width_cm if total_width_cm > 0 else 0
        turns = 0.5 * math.tau
        phase = (1.0 - t) * turns + 0.25 * math.tau
        amp = 0.5 * total_width_cm
        x = left_current_cm * (1.0 - config.curve_pct) + (config.curve_pct) * amp * math.sin(phase)
        z = 0 + config.curve_pct * amp * math.cos(phase)

        transform.translate = Gf.Vec3d(x, top_current_cm, z)

        angle = -config.curve_pct * math.degrees(-phase + 0.5 * math.tau)
        # print(t, phase, angle)

        transform.rotate = Gf.Vec3d(0, angle, 0)

        transforms[image.filename] = transform

        left_current_cm += max_image_width_cm + image_gap_cm
        seen += 1
    return transforms

def create_image_sequence_group_prim(stage: Usd.Stage, root_prim_path: Sdf.Path, config: Config) -> Usd.Prim:
    # Create the root prim
    prim: Usd.Prim = stage.GetPrimAtPath(root_prim_path)
    if not prim.IsValid():
        xform: UsdGeom.Xform = UsdGeom.Xform.Define(stage, root_prim_path)
        Usd.ModelAPI(xform).SetKind(Kind.Tokens.component)
        translate_op: UsdGeom.XformOp = xform.AddTranslateOp()
        rotate_op: UsdGeom.XformOp = xform.AddRotateXYZOp()
        scale_op: UsdGeom.XformOp = xform.AddScaleOp()
        translate_op.Set(Gf.Vec3d(0, 0, 0))
        rotate_op.Set(Gf.Vec3d(0, 0, 0))
        scale_op.Set(Gf.Vec3d(1, 1, 1))
    # Persist the config data in the top-level USD prim
    prim: Usd.Prim = stage.GetPrimAtPath(root_prim_path)
    set_config_metadata(prim, config)


    # Create a child prim for each image
    transforms = calculate_transforms(config)
    for asset_path in config.expanded_glob:
        image_path = Path(asset_path)
        transform: Transform = transforms[asset_path]
        # Create the prim
        image_prim_path = root_prim_path.AppendChild(make_safe_prim_name(image_path.stem))
        create_textured_quad_prim(
            stage=stage,
            prim_path=image_prim_path,
            translate=transform.translate,
            scale=transform.scale,
            rotate=transform.rotate,
            image_path=asset_path,
        )
    return prim

def update_image_sequence_prims(stage: Usd.Stage, root_prim_path: Sdf.Path, config: Config) -> None:
    if stage is None:
        carb.log_warn("Unexpected: stage is none")
        return
    top_prim: Usd.Prim = stage.GetPrimAtPath(root_prim_path)
    if not top_prim.IsValid():
        carb.log_warn("Unexpected: prim is invalid")
        return
    set_config_metadata(top_prim, config)
    transforms = calculate_transforms(config)
    # Create a child prim for each image
    for image in config.expanded_glob:
        image_path = Path(image)
        transform: Transform = transforms[image]
        image_prim_path: Sdf.Path = root_prim_path.AppendChild(make_safe_prim_name(image_path.stem))
        mesh_prim_path: Sdf.Path = image_prim_path.AppendChild("ImageSequenceMesh")
        image_prim: Usd.Prim = stage.GetPrimAtPath(image_prim_path)
        mesh_prim: Usd.Prim = stage.GetPrimAtPath(mesh_prim_path)
        if not image_prim.IsValid():
            carb.log_warn(f"Unexpected: {image_prim_path} is invalid")
            return
        if not mesh_prim.IsValid():
            carb.log_warn(f"Unexpected: {mesh_prim_path} is invalid")
            return
        image_prim.GetAttribute("xformOp:translate").Set(transform.translate)
        mesh_prim.GetAttribute("xformOp:scale").Set(transform.scale)
        image_prim.GetAttribute("xformOp:rotateXYZ").Set(transform.rotate)
    return

def make_safe_prim_name(name: str, replace: str = "_") -> str:
    for c in ["-", ".", "?"]:
        name = name.replace(c, replace)
    return name
