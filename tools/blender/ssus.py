"""SS United States shots, built in code.

Usage: python3 tools/blender/ssus.py <mode> <out.mp4> [--frames 48] [--res 540x960] [--samples 12]
  mode = sail     liner steaming at speed, camera tracking alongside
         sink     funnels removed, liner flooding and settling level into the sea
         seafloor liner resting upright on the sand, underwater, camera drifting
"""
import argparse, math, shutil, subprocess, sys, tempfile
from pathlib import Path
import bpy

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["sail", "sink", "seafloor"])
ap.add_argument("out")
ap.add_argument("--frames", type=int, default=48)
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--res", default="540x960")
ap.add_argument("--samples", type=int, default=12)
a = ap.parse_args(sys.argv[1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
N = a.frames


def mat(name, rgb, rough=0.5, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def add(obj, material, parent):
    obj.data.materials.append(material)
    obj.parent = parent
    return obj


def box(loc, scale, material, parent, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.scale = scale
    if bevel:
        m = o.modifiers.new("bevel", "BEVEL")
        m.width, m.segments = bevel, 2
    return add(o, material, parent)


hull_m = mat("hull", (0.02, 0.02, 0.025), 0.45, 0.2)
boot_m = mat("boot", (0.45, 0.05, 0.04), 0.5)
white_m = mat("white", (0.9, 0.9, 0.88), 0.35)
red_m = mat("red", (0.75, 0.06, 0.05), 0.4)
blue_m = mat("blue", (0.03, 0.08, 0.35), 0.4)
rust_m = mat("rust", (0.35, 0.18, 0.1), 0.8)

# Ship, ~990 ft scaled to 20 units long. Origin at the ship's centre.
bpy.ops.object.empty_add(location=(0, 0, 0))
ship = bpy.context.object

hull = box((0, 0, 0), (10, 1.05, 0.9), hull_m, ship, 0.3)
box((0, 0, -0.72), (10.02, 1.06, 0.2), boot_m, ship, 0.1)
box((0.8, 0, 1.15), (7.2, 0.95, 0.32), white_m, ship, 0.08)
box((1.2, 0, 1.75), (5.4, 0.85, 0.3), white_m, ship, 0.06)
box((1.6, 0, 2.3), (3.4, 0.7, 0.26), white_m, ship, 0.05)
box((-2.6, 0, 2.75), (0.6, 0.6, 0.2), white_m, ship, 0.04)  # bridge

funnels = []
if a.mode == "sail":
    for x in (-0.6, 3.4):  # two big funnels: red top, white, blue base
        for z, h, m_ in ((3.1, 0.55, blue_m), (3.75, 0.75, white_m), (4.45, 0.65, red_m)):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.75, depth=h, location=(x, 0, z))
            f = add(bpy.context.object, m_, ship)
            f.scale = (1.5, 0.95, 1)
            funnels.append(f)
else:
    for x in (-0.6, 3.4):  # funnels cut down before the sinking
        bpy.ops.mesh.primitive_cylinder_add(radius=0.75, depth=0.4, location=(x, 0, 2.75))
        f = add(bpy.context.object, rust_m, ship)
        f.scale = (1.5, 0.95, 1)

w, h = map(int, a.res.split("x"))
scene.render.resolution_x, scene.render.resolution_y = w, h
scene.frame_start, scene.frame_end = 1, N
scene.render.fps = a.fps
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
world = bpy.data.worlds.new("w")
scene.world = world
bg = world.node_tree.nodes["Background"]

bpy.ops.object.camera_add()
cam = bpy.context.object
scene.camera = cam
cam.data.lens = 32


def key(obj, frame, loc=None, rot=None):
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=frame)
    if rot is not None:
        obj.rotation_euler = [math.radians(r) for r in rot]
        obj.keyframe_insert("rotation_euler", frame=frame)


def linear(*objs):
    for o in objs:
        if o.animation_data and o.animation_data.action:
            for layer in getattr(o.animation_data.action, "layers", []):
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for fc in bag.fcurves:
                            for kp in fc.keyframe_points:
                                kp.interpolation = "LINEAR"
            for fc in getattr(o.animation_data.action, "fcurves", []):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


if a.mode in ("sail", "sink"):
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, -0.35))
    bpy.context.object.data.materials.append(mat("sea", (0.03, 0.2, 0.3), 0.06))
    bg.inputs[0].default_value = (0.55, 0.68, 0.8, 1) if a.mode == "sail" else (0.42, 0.5, 0.58, 1)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(35)))
    bpy.context.object.data.energy = 4 if a.mode == "sail" else 2.5

if a.mode == "sail":
    # Ship moves -x fast; camera tracks alongside, slowly drifting toward the bow.
    key(ship, 1, loc=(0, 0, 0)); key(ship, N, loc=(-30, 0, 0))
    key(cam, 1, loc=(6, -22, 3.5), rot=(84, 0, 12)); key(cam, N, loc=(-30, -19, 3.0), rot=(85, 0, -6))
    # Bow wave: a white wedge riding at the bow
    bpy.ops.mesh.primitive_cube_add(location=(-12, 0, -0.3))
    wave = add(bpy.context.object, mat("foam", (0.95, 0.97, 1.0), 0.3), ship)
    wave.scale = (1.4, 1.6, 0.08)
    linear(ship, cam)

elif a.mode == "sink":
    # Flooded evenly: settles level, a slight roll, then slips under.
    key(ship, 1, loc=(0, 0, 0), rot=(0, 0, 0))
    key(ship, int(N * 0.55), loc=(0, 0, -1.2), rot=(1.5, 0, 0))
    key(ship, N, loc=(0, 0, -5.5), rot=(0, 0, 0))
    key(cam, 1, loc=(14, -24, 4.5), rot=(80, 0, 30)); key(cam, N, loc=(12, -21, 3.2), rot=(83, 0, 30))
    linear(cam)

else:  # seafloor
    bg.inputs[0].default_value = (0.01, 0.07, 0.11, 1)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -1.0))
    bpy.context.object.data.materials.append(mat("sand", (0.16, 0.15, 0.11), 0.9))
    bpy.ops.object.light_add(type="AREA", location=(0, 0, 30))
    sun = bpy.context.object
    sun.data.energy, sun.data.size, sun.data.color = 14000, 60, (0.45, 0.85, 1.0)
    # Murk: fog the far distance via world volume (cheap, low density)
    vol = world.node_tree.nodes.new("ShaderNodeVolumeScatter")
    vol.inputs["Density"].default_value = 0.035
    vol.inputs["Color"].default_value = (0.2, 0.55, 0.65, 1)
    world.node_tree.links.new(vol.outputs[0], world.node_tree.nodes["World Output"].inputs["Volume"])
    key(cam, 1, loc=(-16, -15, 1.0), rot=(88, 0, -40)); key(cam, N, loc=(-9, -17, 2.2), rot=(84, 0, -22))
    linear(cam)

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
