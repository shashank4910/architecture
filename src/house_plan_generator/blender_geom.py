"""Low-level Blender geometry helpers for the procedural 3D pipeline.

All builders place objects with center-based boxes/cylinders/spheres.
Every created object is unlinked from its original collection and linked to
the scene root collection so the final render sees a flat, predictable scene.
"""

import bpy


def absorb(obj):
    """Move object to the scene root collection (idempotent)."""
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def box(name, cx, cy, cz, sx, sy, sz, mat=None):
    """Axis-aligned box by center + full size (Blender world meters)."""
    bpy.ops.mesh.primitive_cube_add(location=(cx, cy, cz))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx / 2.0, sy / 2.0, sz / 2.0)
    if mat is not None:
        obj.data.materials.append(mat)
    return absorb(obj)


def cyl(name, cx, cy, cz, r, depth, mat=None, verts=24, rot_x=0.0, rot_y=0.0,
        rot_z=0.0, smooth=False):
    """Cylinder by center, radius and full depth."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=(cx, cy, cz))
    obj = bpy.context.active_object
    obj.name = name
    if rot_x or rot_y or rot_z:
        obj.rotation_euler = (rot_x, rot_y, rot_z)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    if mat is not None:
        obj.data.materials.append(mat)
    return absorb(obj)


def sph(name, cx, cy, cz, r, mat=None, smooth=True):
    """UV sphere by center and radius."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=r,
                                         location=(cx, cy, cz))
    obj = bpy.context.active_object
    obj.name = name
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    if mat is not None:
        obj.data.materials.append(mat)
    return absorb(obj)


def rot_pt(dx, dy, ang):
    """Rotate a local 2D offset by ang radians (for rotated furniture)."""
    c, s = __import__("math").cos(ang), __import__("math").sin(ang)
    return dx * c - dy * s, dx * s + dy * c
