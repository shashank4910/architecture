"""Procedural PBR material library for the Blender 3D pipeline — quality upgrade.

Every material is node-based and fully procedural (no external textures).
Canonical plan units are feet.

Upgrades vs the old pipeline:
- Warmer, more architectural color palette
- Subtle per-instance color variation via Object Info random
- Better roughness balance for realistic surfaces
- Better wood grain, better tile grout
- Clearcoat car paint
"""

import math

import bpy

FT2M = 0.3048


def _safe_input(bsdf, name, value):
    """Set a Principled BSDF input if it exists, else silently skip."""
    try:
        bsdf.inputs[name].default_value = value
    except Exception:
        pass


def _new(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, nt, bsdf


def _object_variation(nt, bsdf, hue_shift=0.0, sat_scale=1.0, val_scale=1.0):
    """Add subtle per-instance color variation using Object Info random."""
    if hue_shift == 0.0 and sat_scale == 1.0 and val_scale == 1.0:
        return
    info = nt.nodes.new("ShaderNodeObjectInfo")
    info.location = (-900, 120)
    base = bsdf.inputs["Base Color"].default_value[:4]
    if hue_shift != 0.0 or val_scale != 1.0:
        hue = nt.nodes.new("ShaderNodeHueSaturation")
        hue.location = (-700, 120)
        hue.inputs["Color"].default_value = base
        hue.inputs["Hue"].default_value = hue_shift
        if sat_scale != 1.0:
            hue.inputs["Saturation"].default_value = sat_scale
        nt.links.new(info.outputs["Random"], hue.inputs["Hue"])
        nt.links.new(hue.outputs["Color"], bsdf.inputs["Base Color"])
    elif sat_scale != 1.0:
        sat = nt.nodes.new("ShaderNodeHueSaturation")
        sat.location = (-700, 60)
        sat.inputs["Color"].default_value = base
        sat.inputs["Saturation"].default_value = sat_scale
        nt.links.new(info.outputs["Random"], sat.inputs["Hue"])
        nt.links.new(sat.outputs["Color"], bsdf.inputs["Base Color"])


def _noise_bump(nt, bsdf, scale, strength, detail=4.0):
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-800, 0)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Detail"].default_value = detail
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (-180, -220)
    bump.inputs["Strength"].default_value = strength
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _paint(name, rgb, rough=0.55, noise_scale=18.0, bump=0.04, metallic=0.0,
           var_hue=0.015, var_sat=0.06, var_val=0.04):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Roughness", rough)
    _safe_input(b, "Metallic", metallic)
    if bump > 0:
        _noise_bump(nt, b, noise_scale, bump)
    _object_variation(nt, b, var_hue, var_sat, var_val)
    return mat


def _wood(name, rgb, rough=0.4, plank=9.0, grain=0.18, along="x"):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Roughness", rough)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-900, 0)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-700, 0)
    s = (plank, plank * 0.05, plank) if along == "x" else (plank * 0.05, plank, plank)
    mapping.inputs["Scale"].default_value = s
    wave = nt.nodes.new("ShaderNodeTexNoise")
    wave.location = (-500, 0)
    wave.inputs["Detail"].default_value = 8.0
    wave.inputs["Distortion"].default_value = 2.2
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-300, 60)
    dark = tuple(c * (1.0 - grain) for c in rgb) + (1.0,)
    light = tuple(min(1.0, c * (1.0 + grain * 0.9)) for c in rgb) + (1.0,)
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].color = light
    ramp.color_ramp.interpolation = "B_SPLINE"
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (-100, -260)
    bump.inputs["Strength"].default_value = 0.10
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mat


def _tile(name, rgb, grout_rgb, tile_m=0.6, rough=0.3, mortar=0.10):
    mat, nt, b = _new(name)
    _safe_input(b, "Roughness", rough)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-900, 0)
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.location = (-600, 0)
    brick.offset = 0.0
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = mortar
    brick.inputs["Brick Width"].default_value = tile_m
    brick.inputs["Row Height"].default_value = tile_m
    brick.inputs["Color1"].default_value = (*rgb, 1.0)
    brick.inputs["Color2"].default_value = (
        rgb[0] * 0.96, rgb[1] * 0.96, rgb[2] * 0.96, 1.0)
    brick.inputs["Mortar"].default_value = (*grout_rgb, 1.0)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (-300, -260)
    bump.inputs["Strength"].default_value = 0.14
    nt.links.new(coord.outputs["Object"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(brick.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mat


def _concrete(name, rgb, rough=0.82, scale=6.0):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Roughness", rough)
    _noise_bump(nt, b, scale, 0.08, detail=10.0)
    return mat


def _fabric(name, rgb, rough=0.88, scale=90.0):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Roughness", rough)
    _safe_input(b, "Sheen Weight", 0.5)
    _noise_bump(nt, b, scale, 0.18, detail=8.0)
    return mat


def _metal(name, rgb, rough=0.32):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Metallic", 1.0)
    _safe_input(b, "Roughness", rough)
    _noise_bump(nt, b, 160.0, 0.04)
    return mat


def _glass(name, rgb=(0.82, 0.90, 0.94), rough=0.02, ior=1.45):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Roughness", rough)
    _safe_input(b, "Transmission Weight", 1.0)
    _safe_input(b, "IOR", ior)
    _safe_input(b, "Coat Weight", 0.08)
    _safe_input(b, "Coat Roughness", 0.02)
    return mat


def _leaf(rgb=(0.22, 0.40, 0.18), name="Leaf"):
    mat, nt, b = _new(name)
    _safe_input(b, "Roughness", 0.55)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-500, 0)
    noise.inputs["Scale"].default_value = 8.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-280, 40)
    ramp.color_ramp.elements[0].color = (*rgb, 1.0)
    ramp.color_ramp.elements[1].color = (
        min(1.0, rgb[0] * 1.7), min(1.0, rgb[1] * 1.6), min(1.0, rgb[2] * 1.6), 1.0)
    ramp.color_ramp.interpolation = "B_SPLINE"
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return mat


def _car_paint(name, rgb, rough=0.12):
    """Clearcoat car paint."""
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    _safe_input(b, "Metallic", 0.7)
    _safe_input(b, "Roughness", rough)
    _safe_input(b, "Coat Weight", 0.9)
    _safe_input(b, "Coat Roughness", 0.05)
    _safe_input(b, "Coat IOR", 1.5)
    _noise_bump(nt, b, 200.0, 0.02)
    return mat


def build_materials():
    """Build the full material library; returns name -> material mapping."""
    M = {}
    # architectural shell — warmer, more inviting
    M["wall_paint"] = _paint("WallPaint", (0.86, 0.835, 0.77), 0.58, bump=0.025,
                             var_hue=0.01, var_sat=0.04, var_val=0.03)
    M["wall_ext"] = _paint("WallExt", (0.845, 0.81, 0.74), 0.62, bump=0.035,
                            var_hue=0.012, var_sat=0.05, var_val=0.035)
    M["cut_cap"] = _paint("CutCap", (0.935, 0.905, 0.835), 0.42, bump=0.015)
    M["floor_tile"] = _tile("FloorTile", (0.78, 0.74, 0.68), (0.52, 0.49, 0.44),
                            tile_m=0.8, rough=0.30)
    M["floor_wood"] = _wood("FloorWood", (0.48, 0.32, 0.18), rough=0.35,
                            plank=6.5, along="x")
    M["floor_kitchen"] = _tile("FloorKitchen", (0.81, 0.79, 0.75),
                               (0.57, 0.555, 0.52), tile_m=0.5, rough=0.32)
    M["floor_bath"] = _tile("FloorBath", (0.82, 0.845, 0.86),
                            (0.55, 0.58, 0.59), tile_m=0.32, rough=0.20)
    M["floor_park"] = _concrete("FloorPark", (0.50, 0.495, 0.475), 0.82, 5.0)
    M["floor_stair"] = _wood("FloorStair", (0.44, 0.30, 0.17), rough=0.42,
                              plank=11.0)
    M["ground"] = _concrete("Lawn", (0.175, 0.305, 0.13), 0.9, 1.0)
    M["paving"] = _concrete("Paving", (0.45, 0.44, 0.42), 0.85, 3.5)
    M["boundary"] = _paint("BoundaryWall", (0.785, 0.755, 0.685), 0.68, bump=0.04,
                           var_hue=0.015, var_sat=0.05, var_val=0.04)
    # openings — better wood grain
    M["door_wood"] = _wood("DoorWood", (0.31, 0.19, 0.10), rough=0.38,
                           plank=4.5, along="z", grain=0.22)
    M["door_frame"] = _paint("DoorFrame", (0.905, 0.885, 0.845), 0.40, bump=0.015)
    M["win_frame"] = _paint("WinFrame", (0.915, 0.905, 0.875), 0.36, bump=0.012)
    M["glass"] = _glass("Glass", (0.80, 0.88, 0.92))
    # furniture / fixtures
    M["counter"] = _paint("Counter", (0.885, 0.865, 0.825), 0.22, bump=0.008,
                          var_hue=0.005, var_sat=0.02, var_val=0.02)
    M["cabinet"] = _wood("Cabinet", (0.50, 0.35, 0.19), rough=0.45, plank=5.5,
                          grain=0.20)
    M["cabinet_upper"] = _paint("CabinetUpper", (0.915, 0.895, 0.855), 0.45,
                                 bump=0.015)
    M["steel"] = _metal("Steel", (0.70, 0.71, 0.73), 0.28)
    M["metal_dark"] = _metal("MetalDark", (0.16, 0.16, 0.185), 0.38)
    M["ceramic"] = _paint("Ceramic", (0.925, 0.925, 0.915), 0.14, bump=0.008)
    M["porcelain"] = _paint("Porcelain", (0.95, 0.94, 0.925), 0.18, bump=0.006)
    M["mirror"] = _metal("Mirror", (0.905, 0.915, 0.935), 0.015)
    M["screen"] = _paint("Screen", (0.015, 0.015, 0.02), 0.22, bump=0.0)
    M["terracotta"] = _paint("Terracotta", (0.535, 0.29, 0.19), 0.62, bump=0.04,
                              var_hue=0.02, var_sat=0.06, var_val=0.05)
    # fabrics — warmer, more realistic sheen
    M["fabric_sofa"] = _fabric("FabricSofa", (0.57, 0.53, 0.47))
    M["fabric_cush"] = _fabric("FabricCush", (0.805, 0.785, 0.74))
    M["fabric_bed"] = _fabric("FabricBed", (0.835, 0.815, 0.78))
    M["mattress"] = _fabric("Mattress", (0.905, 0.895, 0.875), 0.78)
    M["rug"] = _fabric("Rug", (0.645, 0.585, 0.505), 0.90, 35.0)
    # woods — richer color
    M["table_wood"] = _wood("TableWood", (0.385, 0.245, 0.135), rough=0.32,
                             plank=7.5, grain=0.22)
    M["stair_wood"] = _wood("StairWood", (0.45, 0.31, 0.175), rough=0.42,
                             plank=9.0, grain=0.20)
    M["puja_wood"] = _wood("PujaWood", (0.345, 0.21, 0.115), rough=0.42,
                            plank=5.5, grain=0.22)
    M["trunk"] = _wood("Trunk", (0.265, 0.18, 0.11), rough=0.82, plank=3.5,
                        grain=0.15)
    M["leaf"] = _leaf()
    # car — better paint
    M["car_paint"] = _car_paint("CarPaint", (0.225, 0.255, 0.315))
    M["car_glass"] = _glass("CarGlass", (0.06, 0.08, 0.11), 0.06)
    M["tire"] = _paint("Tire", (0.02, 0.02, 0.025), 0.88, bump=0.07,
                       var_hue=0.01, var_sat=0.03, var_val=0.02)
    return M
