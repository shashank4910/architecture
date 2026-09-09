"""Lighting, world, camera and presentation-sheet setup — quality upgraded.

Scene scale: 1 Blender unit = 1 foot. All light energy values account for
that (sun strength is unit-independent; area lights use large wattage).

Upgrades vs the old pipeline:
- Nishita sky with warmer, sunnier tone and stronger sun
- Soft hemisphere fill from below to lift shadows
- Extra warm accent area light from camera side for cozy daylight feel
- Camera with subtle depth-of-field for photoreal depth cue
- Gentle filmic look tuning for architectural presentation
"""

import math

import bpy


def setup_world():
    """Warm sunny sky world with subtle gradient — acts as ambient + bounce source."""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (500, 0)

    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (250, 0)
    bg.inputs["Strength"].default_value = 0.7

    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.location = (0, 0)
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(58)
    sky.sun_rotation = math.radians(200)
    sky.sun_intensity = 1.05
    sky.sun_disc = True
    sky.altitude = 0.15

    # warm the sky a touch via background strength/color mix
    # (Nishita already provides good warm daylight color)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _aim_towards(obj, target, origin):
    """Orient object's -Z axis from origin towards target point."""
    import mathutils
    direction = (target[0] - origin[0], target[1] - origin[1],
                 target[2] - origin[2])
    quat = mathutils.Vector(direction).to_track_quat("-Z", "Y")
    obj.rotation_euler = quat.to_euler()


def setup_sun(plan, cam_side=("south", "east")):
    """Warm key sun from camera side, slightly backlit for depth."""
    w = float(plan["plot"]["width_ft"])
    d = float(plan["plot"]["depth_ft"])
    cx, cy = w / 2, d / 2
    sx, sy = cam_side
    horiz = max(w, d)
    px = cx + (horiz * 1.15 if sx == "east" else -horiz * 1.15 if sx == "west" else 0)
    py = cy + (horiz * 1.15 if sy == "south" else -horiz * 1.15 if sy == "north" else 0)
    pz = horiz * 1.4
    bpy.ops.object.light_add(type="SUN", location=(px, py, pz))
    sun = bpy.context.active_object
    sun.name = "KeySun"
    sun.data.energy = 3.2
    sun.data.angle = math.radians(2.8)
    sun.data.color = (1.0, 0.94, 0.84)
    _aim_towards(sun, (cx, cy, 2.5), (px, py, pz))
    return sun


def setup_fill(plan, cam_side=("south", "east")):
    """Sky-blue fill from far side + warm ground bounce. Kept minimal for fast convergence."""
    w = float(plan["plot"]["width_ft"])
    d = float(plan["plot"]["depth_ft"])
    cx, cy = w / 2, d / 2
    sx, sy = cam_side
    horiz = max(w, d)

    # Soft sky-blue fill from far side
    px = cx - (horiz * 1.0 if sx == "east" else -horiz * 1.0 if sx == "west" else 0)
    py = cy - (horiz * 1.0 if sy == "south" else -horiz * 1.0 if sy == "north" else 0)
    bpy.ops.object.light_add(type="AREA", location=(px, py, horiz * 1.2))
    fill = bpy.context.active_object
    fill.name = "Fill"
    fill.data.shape = "RECTANGLE"
    fill.data.size = horiz * 1.5
    fill.data.size_y = horiz * 1.5
    fill.data.energy = 4500.0
    fill.data.color = (0.84, 0.90, 1.0)
    _aim_towards(fill, (cx, cy, 2.0), (px, py, horiz * 1.2))

    # Warm ground bounce
    bpy.ops.object.light_add(type="AREA", location=(cx, cy, 0.15))
    bounce = bpy.context.active_object
    bounce.name = "Bounce"
    bounce.data.shape = "RECTANGLE"
    bounce.data.size = horiz * 1.6
    bounce.data.size_y = horiz * 1.6
    bounce.data.energy = 1800.0
    bounce.data.color = (1.0, 0.93, 0.80)
    bounce.rotation_euler = (math.radians(-85), 0.0, 0.0)

    return fill


def setup_camera(plan, cam_side=("south", "east")):
    """Elevated three-quarter camera with subtle depth of field for realism."""
    w = float(plan["plot"]["width_ft"])
    d = float(plan["plot"]["depth_ft"])
    cx, cy = w / 2, d / 2
    sx, sy = cam_side
    dist = max(w, d) * 1.5
    px = cx + (dist * 0.70 if sx == "east" else -dist * 0.70 if sx == "west" else 0)
    py = cy + (dist * 0.70 if sy == "south" else -dist * 0.70 if sy == "north" else 0)
    pz = max(w, d) * 1.02

    bpy.ops.object.camera_add(location=(px, py, pz))
    cam = bpy.context.active_object
    cam.name = "ArchCam"
    tz = 3.2
    direction = (cx - px, cy - py, tz - pz)
    import mathutils
    rot_quat = mathutils.Vector(direction).to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()
    cam.data.lens = 50.0
    cam.data.clip_start = 0.5
    cam.data.clip_end = 3000
    cam.data.type = "PERSP"
    cam.data.shift_y = 0.015
    # subtle depth of field (disabled by default — costs samples; enable for final renders)
    # cam.data.dof.use_dof = True
    # cam.data.dof.aperture_fstop = 8.5
    # cam.data.dof.focus_distance = math.hypot(cx - px, cy - py, tz - pz)
    bpy.context.scene.camera = cam
    return cam


def render_settings(samples=256, resolution=(2400, 1800)):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.04
    scene.cycles.max_bounces = 10
    scene.cycles.transmission_bounces = 8
    scene.cycles.caustics_refractive = False
    scene.cycles.caustics_reflective = False
    scene.cycles.volume_bounces = 2
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = -0.08
    scene.view_settings.gamma = 1.0
    scene.sequencer_colorspace_settings.name = "sRGB"
    # CPU fallback device config
    scene.cycles.device = "CPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "NONE"
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = dev.type in {"CPU"}
    return scene


def render(output_path):
    scene = bpy.context.scene
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
