"""Example 3D shot built entirely in code: an ocean liner settling bow-first.

Usage: python3 tools/blender/liner.py <out.mp4> [--frames 72] [--res 540x960] [--samples 16]

Runs Blender as a Python module (pip install bpy); no Blender app or GPU needed.
Copy this file as a starting point for other shots: build objects, keyframe them, render.
"""
import argparse, math, shutil, subprocess, sys, tempfile
from pathlib import Path
import bpy

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--frames", type=int, default=72)
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--res", default="540x960")
ap.add_argument("--samples", type=int, default=16)
a = ap.parse_args(sys.argv[1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def mat(name, rgb, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def box(name, loc, scale, material, parent=None, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name, o.scale = name, scale
    o.data.materials.append(material)
    if bevel:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = bevel, 3
    if parent:
        o.parent = parent
    return o


hull_m = mat("hull", (0.05, 0.06, 0.08), 0.4, 0.3)
red_m = mat("waterline", (0.55, 0.06, 0.05), 0.5)
white_m = mat("superstructure", (0.92, 0.92, 0.9), 0.35)
funnel_m = mat("funnel", (0.75, 0.1, 0.08), 0.4)
sea_m = mat("sea", (0.08, 0.32, 0.38), 0.08)

# Ship: an empty pivot near the stern so the bow dips first.
bpy.ops.object.empty_add(location=(4, 0, 0))
ship = bpy.context.object
ship.name = "ship"
box("hull", (-4, 0, 0.0), (6, 0.9, 0.7), hull_m, ship, 0.25)
box("boot", (-4, 0, -0.55), (6.02, 0.92, 0.18), red_m, ship, 0.1)
box("deck1", (-4.3, 0, 0.95), (4.2, 0.75, 0.3), white_m, ship, 0.08)
box("deck2", (-4.3, 0, 1.45), (3.0, 0.65, 0.25), white_m, ship, 0.06)
for i, x in enumerate((-6.0, -3.6)):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.38, depth=1.4, location=(x, 0, 2.3))
    f = bpy.context.object
    f.name, f.scale = f"funnel{i}", (1.2, 1, 1)
    f.data.materials.append(funnel_m)
    f.parent = ship

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.3))
bpy.context.object.data.materials.append(sea_m)

# Keyframes: float level, then the bow drops and the ship settles.
end = a.frames
for frame, z, tilt in ((1, 0, 0), (int(end * 0.25), -0.05, 0), (end, -1.6, 14)):
    ship.location.z = z
    ship.rotation_euler.y = math.radians(-tilt)
    ship.keyframe_insert("location", frame=frame)
    ship.keyframe_insert("rotation_euler", frame=frame)

# Light, sky, camera.
bpy.ops.object.light_add(type="SUN", location=(0, 0, 20), rotation=(math.radians(50), 0, math.radians(30)))
bpy.context.object.data.energy = 4
world = bpy.data.worlds.new("sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.7, 0.8, 1)
scene.world = world
bpy.ops.object.camera_add(location=(9, -16, 3.2), rotation=(math.radians(82), 0, math.radians(30)))
scene.camera = bpy.context.object
scene.camera.data.lens = 38

w, h = map(int, a.res.split("x"))
scene.render.resolution_x, scene.render.resolution_y = w, h
scene.frame_start, scene.frame_end = 1, end
scene.render.fps = a.fps
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True

tmp = Path(tempfile.mkdtemp())
scene.render.filepath = str(tmp / "f_")
scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(animation=True)

out = Path(a.out).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps), "-i", str(tmp / "f_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)], check=True)
shutil.rmtree(tmp)
print("wrote", out)
