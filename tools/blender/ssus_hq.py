"""SS United States — high-quality shots, built entirely in code.

Usage (via the wrapper, which runs Blender headless on the GPU when available):
  python tools/render_shot.py tools/blender/ssus_hq.py <shot> <out.mp4> --seconds 5.1
         [--engine eevee|cycles] [--fps 24] [--res 1080x1920] [--samples N] [--still FRAME.png]

  --engine eevee   fast, uses any GPU (Intel Arc, AMD, NVIDIA, Apple). Default.
  --engine cycles  path-traced; uses OptiX/CUDA/HIP/oneAPI/Metal if Blender finds a GPU, else CPU.
  --fps            below 24, frames are motion-interpolated up to 24 (saves render time).
  --still          renders one frame (at --at, 0-1 through the shot) for look-dev.

Shots:
  hero      aerial chase at speed, low golden sun, wake            (hook)
  side      low tracking shot along the hull at speed              (record)
  pier      laid up at a pier, overcast, rusting, slow push-in     (laidup)
  flood     funnels cut down, riding low, slow orbit, grey sea     (flood)
  sink      settles level and slips under                          (down)
  reef      underwater: resting upright on the sand, camera glide  (reef)

Units: 1 = 10 m. The ship is 30.2 long (302 m / 990 ft), 3.1 wide.
"""
import argparse, math, random, shutil, subprocess, sys, tempfile
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import script_args, ffmpeg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("shot", choices=["hero", "side", "pier", "flood", "sink", "reef"])
ap.add_argument("out")
ap.add_argument("--seconds", type=float, default=5.0)
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--res", default="1080x1920")
ap.add_argument("--engine", choices=["eevee", "cycles"], default="eevee")
ap.add_argument("--samples", type=int, default=0, help="0 = engine default (eevee 64, cycles 24)")
ap.add_argument("--still", default=None, help="render only this fraction of the shot (0-1) to a PNG")
ap.add_argument("--at", type=float, default=0.5)
a = ap.parse_args(script_args())
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
FPS = a.fps
N = max(2, round(a.seconds * FPS))
SHOT = a.shot
WEATHERED = SHOT in ("pier", "flood", "sink", "reef")
CUT_FUNNELS = SHOT in ("flood", "sink", "reef")

# ----------------------------------------------------------------- materials
def node_mat(name):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def solid(name, rgb, rough=0.5, metal=0.0):
    m, nt, b = node_mat(name)
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def weather(nt, b, base_rgb, rust_rgb=(0.28, 0.12, 0.05), amount=0.55, scale=6.0):
    """Mix rust streaks into a material (vertical streaks: noise stretched along z)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale * 0.12)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 1 - amount
    ramp.color_ramp.elements[1].position = min(1, 1 - amount + 0.25)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*base_rgb, 1)
    mix.inputs[7].default_value = (*rust_rgb, 1)
    L = nt.links
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    L.new(mp.outputs["Vector"], nz.inputs["Vector"])
    L.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], mix.inputs["Factor"])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.75


def hull_material():
    """Black topsides, red boot-topping below the waterline, thin white sheer line."""
    m, nt, b = node_mat("hull")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    under = nt.nodes.new("ShaderNodeMath"); under.operation = "LESS_THAN"; under.inputs[1].default_value = -0.72
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    black = (0.012, 0.013, 0.016) if not WEATHERED else (0.035, 0.03, 0.028)
    mix.inputs[6].default_value = (*black, 1)
    mix.inputs[7].default_value = (0.42, 0.04, 0.03, 1)
    L = nt.links
    L.new(tc.outputs["Object"], sep.inputs["Vector"])
    L.new(sep.outputs["Z"], under.inputs[0])
    L.new(under.outputs[0], mix.inputs["Factor"])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.42 if not WEATHERED else 0.7
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.25
    if WEATHERED:
        weather(nt, b, black, amount=0.35)
        # keep the red bottom: re-mix after weathering
        mix2 = nt.nodes.new("ShaderNodeMix"); mix2.data_type = "RGBA"
        mix2.inputs[7].default_value = (0.3, 0.06, 0.04, 1)
        L.new(b.inputs["Base Color"].links[0].from_socket, mix2.inputs[6])
        L.new(under.outputs[0], mix2.inputs["Factor"])
        L.new(mix2.outputs[2], b.inputs["Base Color"])
    return m


def windows_material(name="superstructure"):
    """White superstructure with rows of dark windows (brick texture on object x/z)."""
    m, nt, b = node_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (math.radians(90), 0, 0)  # x,z plane -> brick u,v
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 9.0
    br.inputs["Mortar Size"].default_value = 0.035
    br.inputs["Brick Width"].default_value = 0.35
    br.inputs["Row Height"].default_value = 0.42
    white = (0.86, 0.86, 0.83) if not WEATHERED else (0.62, 0.58, 0.52)
    br.inputs["Color1"].default_value = (0.05, 0.07, 0.09, 1)
    br.inputs["Color2"].default_value = (0.06, 0.08, 0.1, 1)
    br.inputs["Mortar"].default_value = (*white, 1)
    L = nt.links
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    L.new(mp.outputs["Vector"], br.inputs["Vector"])
    L.new(br.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.3
    return m


HULL = hull_material()
SUPER = windows_material()
WHITE = solid("white", (0.86, 0.86, 0.83) if not WEATHERED else (0.6, 0.56, 0.5), 0.35)
DECK = solid("deck", (0.55, 0.52, 0.47), 0.7)
RED = solid("red", (0.62, 0.04, 0.03), 0.4)
BLUE = solid("blue", (0.02, 0.05, 0.22), 0.4)
BOAT = solid("lifeboat", (0.85, 0.42, 0.08) if not WEATHERED else (0.5, 0.3, 0.15), 0.5)
DARK = solid("dark", (0.04, 0.04, 0.045), 0.5, 0.4)
RUSTY = solid("rusty", (0.3, 0.14, 0.07), 0.85)
if WEATHERED:
    for mm, base in ((WHITE, (0.6, 0.56, 0.5)), (RED, (0.4, 0.1, 0.06)), (BLUE, (0.06, 0.07, 0.15))):
        weather(mm.node_tree, mm.node_tree.nodes["Principled BSDF"], base, amount=0.45)

# ----------------------------------------------------------------- ship
ship = bpy.data.objects.new("ship", None)
S.collection.objects.link(ship)


def link(obj, mat, parent=ship):
    if mat is not None:
        obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def hull_mesh():
    """Loft U-shaped sections along x. Bow at -x (sharp, raked), stern at +x (rounded)."""
    L, B, D = 30.2, 3.1, 2.1  # length, beam, depth (keel z=-1.25 .. deck z=0.85)
    zk, zd = -1.25, 0.85
    stations = 48
    ring = 14
    bm = bmesh.new()
    rings = []
    for i in range(stations + 1):
        u = i / stations  # 0 bow .. 1 stern
        x = -L / 2 + u * L
        if u < 0.28:  # fine entry
            k = u / 0.28
            w = (B / 2) * (1 - (1 - k) ** 2.2)
        elif u > 0.9:  # rounded cruiser stern
            k = (u - 0.9) / 0.1
            w = (B / 2) * math.sqrt(max(0.0, 1 - k ** 2 * 0.85))
        else:
            w = B / 2
        w = max(w, 0.02)
        sheer = 0.35 * (1 - u) ** 3  # deck rises toward the bow
        rake = 0.0
        if u < 0.06:  # raked stem: keel rises toward the bow
            rake = (0.06 - u) / 0.06 * 1.4
        top = zd + sheer
        bot = zk + rake
        pts = []
        for j in range(ring + 1):
            t = j / ring  # 0 = port deck edge, 1 = starboard deck edge, around the bottom
            ang = math.pi * t
            y = -math.cos(ang) * w
            # U section: flat-ish bottom, vertical sides
            s = math.sin(ang)
            z = top - (top - bot) * (s ** 0.35)
            pts.append(bm.verts.new((x, y, z)))
        rings.append(pts)
    for i in range(stations):
        for j in range(ring):
            bm.faces.new((rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]))
    # deck cap
    deck = [r[0] for r in rings] + [r[-1] for r in reversed(rings)]
    bm.faces.new(deck)
    bm.normal_update()
    me = bpy.data.meshes.new("hull")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("hull", me)
    S.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


hull = link(hull_mesh(), HULL)
hull.data.materials.append(DECK)
hull.data.polygons[-1].material_index = 1
sub = hull.modifiers.new("sub", "SUBSURF"); sub.levels = 1; sub.render_levels = 2


def box(name, loc, size, mat, bevel=0.04, parent=ship):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        m = o.modifiers.new("bevel", "BEVEL"); m.width, m.segments = bevel, 2
    return link(o, mat, parent)


def rounded_tier(name, x0, x1, z, h, half_w, mat):
    """Superstructure tier with a rounded forward face."""
    length = x1 - x0
    b = box(name, ((x0 + x1) / 2 + 0.3, 0, z + h / 2), (length - 0.6, half_w * 2, h), mat, 0.03)
    bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=half_w, depth=h, location=(x0 + half_w * 0.9, 0, z + h / 2))
    c = bpy.context.object
    c.scale = (0.9, 1, 1)
    link(c, mat)
    return b


# Superstructure tiers (forward end toward bow at -x). Ship centre ~ x=0.
z = 0.85
tiers = [(-8.6, 9.6, 0.5, 1.42), (-7.8, 8.4, 0.46, 1.32), (-6.9, 6.4, 0.44, 1.2), (-6.0, 4.2, 0.4, 1.05), (-5.4, 1.6, 0.32, 0.85)]
for i, (x0, x1, h, hw) in enumerate(tiers):
    rounded_tier(f"tier{i}", x0, x1, z, h, hw, SUPER if i < 3 else WHITE)
    box(f"tierdeck{i}", ((x0 + x1) / 2 + 0.2, 0, z + h + 0.012), (x1 - x0 - 0.2, hw * 2 + 0.06, 0.025), DECK, 0)
    z += h
# Bridge with wings
box("bridge", (-5.3, 0, z + 0.14), (0.9, 1.9, 0.28), SUPER, 0.03)
box("wings", (-5.15, 0, z + 0.24), (0.35, 3.0, 0.06), WHITE, 0.01)
# Forecastle machinery + aft decks
for x in (-12.5, -11.4):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.18, location=(x, 0.5, 0.98)); link(bpy.context.object, DARK)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.18, location=(x, -0.5, 0.98)); link(bpy.context.object, DARK)
box("aftdeckhouse", (11.0, 0, 1.0), (2.2, 1.6, 0.3), WHITE, 0.03)

# Lifeboats on davits, both sides of tier 2 deck
for side in (1, -1):
    for k in range(9):
        x = -4.6 + k * 1.15
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.5, location=(x, side * 1.48, 2.0))
        lb = bpy.context.object
        lb.scale = (0.85, 0.24, 0.17)
        link(lb, BOAT)
        box(f"davit{side}{k}", (x, side * 1.36, 2.14), (0.05, 0.3, 0.05), DARK, 0)

# Masts
for x, h in ((-6.2, 2.4), (7.4, 1.5)):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=h, location=(x, 0, z + h / 2)); link(bpy.context.object, DARK)
    box(f"yard{x}", (x, 0, z + h * 0.8), (0.04, 1.1, 0.04), DARK, 0)


def funnel(x, cut=False):
    """Elliptical funnel: blue base, white band, red top, with the winged 'sampan' top."""
    base_z = 2.85
    if cut:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=0.45, location=(x, 0, base_z + 0.22))
        f = bpy.context.object; f.scale = (1.45, 0.62, 1); link(f, RUSTY)
        return
    parts = ((0.55, BLUE), (1.05, WHITE), (1.05, RED))
    zc = base_z
    for h, mat in parts:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=h, location=(x, 0, zc + h / 2))
        f = bpy.context.object
        f.scale = (1.45, 0.62, 1)
        f.rotation_euler.y = math.radians(-6)  # slight rake aft
        link(f, mat)
        zc += h
    box(f"cap{x}", (x + 0.2, 0, zc + 0.02), (2.4, 0.9, 0.06), DARK, 0.02)


funnel(-1.6, CUT_FUNNELS)
funnel(3.6, CUT_FUNNELS)

# ----------------------------------------------------------------- world


def use_gpu_for_cycles():
    """Pick the best Cycles GPU backend Blender reports; returns a description."""
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except Exception:
        return "CPU (no Cycles preferences)"
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            S.cycles.device = "GPU"
            return f"{kind}: " + ", ".join(d.name for d in gpus)
    S.cycles.device = "CPU"
    return "CPU"


if a.engine == "cycles":
    S.render.engine = "CYCLES"
    print("cycles device:", use_gpu_for_cycles())
    S.cycles.samples = a.samples or 24
    S.cycles.use_adaptive_sampling = True
    S.cycles.adaptive_threshold = 0.04
    S.cycles.use_denoising = True
    S.cycles.max_bounces = 4
    S.cycles.diffuse_bounces = 2
    S.cycles.glossy_bounces = 2
    S.cycles.transmission_bounces = 2
    S.cycles.caustics_reflective = S.cycles.caustics_refractive = False
else:
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    S.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    ee = S.eevee
    ee.taa_render_samples = a.samples or 64
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("use_volumetric_shadows", True),
                      ("shadow_ray_count", 2), ("shadow_step_count", 8), ("volumetric_tile_size", "4"),
                      ("volumetric_samples", 96), ("use_gtao", True), ("use_bloom", False)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except Exception:
                pass
    if hasattr(ee, "ray_tracing_options"):
        ee.ray_tracing_options.resolution_scale = "1"
    print("engine:", S.render.engine)
S.render.use_persistent_data = True
S.view_settings.view_transform = "AgX"
S.view_settings.look = "AgX - Medium High Contrast"
S.view_settings.exposure = {"hero": -2.2, "side": -2.2, "pier": -2.6, "flood": -1.6, "sink": -1.6, "reef": -0.6}[SHOT]
w, h = map(int, a.res.split("x"))
S.render.resolution_x, S.render.resolution_y = w, h
S.render.fps = FPS
S.frame_start, S.frame_end = 1, N

world = bpy.data.worlds.new("world")
S.world = world
wn, wl = world.node_tree.nodes, world.node_tree.links
bg = wn["Background"]


def sky(sun_elev, sun_rot, strength=1.0, haze=1.0):
    try:
        sk = wn.new("ShaderNodeTexSky")
        for t in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING"):
            try:
                sk.sky_type = t
                break
            except TypeError:
                continue
        sk.sun_elevation = math.radians(sun_elev)
        sk.sun_rotation = math.radians(sun_rot)
        sk.air_density = 1.0
        sk.aerosol_density = haze
        sk.sun_intensity = 1.0
        wl.new(sk.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = strength
    except Exception as e:  # fallback: flat colour
        print("sky fallback:", e)
        bg.inputs[0].default_value = (0.5, 0.65, 0.8, 1)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(90 - sun_elev), 0, math.radians(sun_rot + 90)))
    sun = bpy.context.object
    sun.data.energy = 4.0 * strength
    sun.data.angle = math.radians(1.5)
    return sun


def ocean(size=90, scale=1.0, choppy=1.0, wind=12, res=18, frames=N, foam=True, speed=1.0, rgb=(0.01, 0.05, 0.07)):
    bpy.ops.mesh.primitive_plane_add(size=2, location=(-size * 2, -size * 2, -0.62))
    o = bpy.context.object
    o.name = "ocean"
    m = o.modifiers.new("ocean", "OCEAN")
    m.geometry_mode = "GENERATE"
    m.size = 1.0
    m.repeat_x = m.repeat_y = 4
    m.spatial_size = size
    m.resolution = res
    m.wave_scale = scale
    m.choppiness = choppy
    m.wind_velocity = wind
    m.use_normals = True
    if foam:
        m.use_foam = True
        m.foam_layer_name = "foam"
        m.foam_coverage = 0.0
    m.time = 1.0
    m.keyframe_insert("time", frame=1)
    m.time = 1.0 + speed * frames / FPS
    m.keyframe_insert("time", frame=frames)
    mat, nt, b = node_mat("sea")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.04
    b.inputs["Specular IOR Level"].default_value = 0.6
    if foam:
        at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "foam"
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.72
        ramp.color_ramp.elements[1].position = 1.0
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        mix.inputs[6].default_value = (*rgb, 1)
        mix.inputs[7].default_value = (0.8, 0.85, 0.85, 1)
        nt.links.new(at.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], mix.inputs["Factor"])
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def wake(length=40, width=5.0):
    """Foam trail behind the stern and bow wave, parented to the ship."""
    mat, nt, b = node_mat("wake")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6; nz.inputs["Detail"].default_value = 10
    grad = nt.nodes.new("ShaderNodeTexGradient")
    mp = nt.nodes.new("ShaderNodeMapping")
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25; ramp.color_ramp.elements[1].position = 0.6
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mixs = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes["Material Output"]
    b.inputs["Base Color"].default_value = (0.85, 0.9, 0.9, 1)
    b.inputs["Roughness"].default_value = 0.6
    L = nt.links
    L.new(tc.outputs["UV"], nz.inputs["Vector"])
    L.new(tc.outputs["UV"], mp.inputs["Vector"])
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(180))
    mp.inputs["Location"].default_value = (1, 1, 0)
    L.new(mp.outputs["Vector"], grad.inputs["Vector"])
    L.new(nz.outputs["Fac"], mul.inputs[0])
    L.new(grad.outputs["Fac"], mul.inputs[1])
    L.new(mul.outputs[0], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], mixs.inputs["Fac"])
    L.new(tr.outputs[0], mixs.inputs[1])
    L.new(b.outputs[0], mixs.inputs[2])
    L.new(mixs.outputs[0], out.inputs["Surface"])
    bpy.ops.mesh.primitive_plane_add(size=1, location=(15 + length / 2, 0, -0.5))
    p = bpy.context.object
    p.scale = (length, width, 1)
    link(p, mat)
    # bow wave
    for side in (1, -1):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(-13.0, side * 1.6, -0.5))
        q = bpy.context.object
        q.scale = (5, 1.4, 1)
        q.rotation_euler.z = side * math.radians(14)
        link(q, mat)


def camera(lens=35):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("cam", cam_data)
    S.collection.objects.link(cam)
    S.camera = cam
    return cam


def look_key(cam, frame, pos, target):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("rotation_euler", frame=frame)


def ship_key(frame, loc, rot=(0, 0, 0)):
    ship.location = loc
    ship.rotation_euler = [math.radians(r) for r in rot]
    ship.keyframe_insert("location", frame=frame)
    ship.keyframe_insert("rotation_euler", frame=frame)


def bob(amp=0.05, roll=0.6, period=6.0, base=(0, 0, 0), drift=(0, 0, 0), sink=None):
    """Keyframe gentle heave/roll every few frames (deterministic)."""
    step = max(1, FPS // 4)
    for f in range(1, N + 1, step):
        t = (f - 1) / FPS
        u = (f - 1) / max(1, N - 1)
        z = base[2] + amp * math.sin(2 * math.pi * t / period)
        if sink:
            z += sink(u)
        ship_key(f, (base[0] + drift[0] * t, base[1] + drift[1] * t, z),
                 (roll * math.sin(2 * math.pi * t / (period * 1.3)), 0.25 * math.sin(2 * math.pi * t / period), 0))


SPEED = 3.0  # units/s while steaming (just for visual motion)
cam = camera()

if SHOT == "hero":
    sky(9, 200, 1.0, 1.2)
    ocean(wind=12, scale=1.1)
    wake()
    bob(amp=0.03, roll=0.4, drift=(-SPEED, 0, 0))
    T = a.seconds
    look_key(cam, 1, (6, -26, 11), (-2, 0, 0.5))
    look_key(cam, N, (6 - SPEED * T - 8, -18, 6), (-SPEED * T - 4, 0, 1.2))
    cam.data.lens = 32
elif SHOT == "side":
    sky(14, 160, 1.0, 1.0)
    ocean(wind=13, scale=1.2)
    wake()
    bob(amp=0.03, roll=0.4, drift=(-SPEED, 0, 0))
    T = a.seconds
    # low camera just above the water, sliding from stern toward the bow
    look_key(cam, 1, (10, -9, 0.6), (4, 0, 2.0))
    look_key(cam, N, (-SPEED * T - 9, -8.5, 0.9), (-SPEED * T - 4, 0, 1.6))
    cam.data.lens = 28
elif SHOT == "pier":
    sky(25, 120, 0.45, 4.0)
    ocean(wind=4, scale=0.3, choppy=0.4, foam=False, rgb=(0.02, 0.035, 0.03))
    pier = solid("concrete", (0.17, 0.165, 0.155), 0.9)
    box("pier", (0, 2.8 + 3.5, -0.3), (60, 7, 1.2), pier, 0, parent=None)
    for k in range(10):
        box(f"bollard{k}", (-13 + k * 3, 2.9, 0.4), (0.18, 0.18, 0.25), DARK, 0.02, parent=None)
    box("shed", (4, 9.5, 1.6), (22, 4, 3.6), solid("shed", (0.45, 0.42, 0.38), 0.9), 0.05, parent=None)
    bob(amp=0.005, roll=0.05, period=9)
    look_key(cam, 1, (-26, 16, 7.5), (-2, 0, 1.4))
    look_key(cam, N, (-21, 13, 6.2), (-2, 0, 1.4))
    cam.data.lens = 35
elif SHOT == "flood":
    sky(18, 230, 0.6, 3.0)
    ocean(wind=9, scale=0.8, rgb=(0.012, 0.04, 0.05))
    bob(amp=0.03, roll=0.8, period=7, base=(0, 0, -0.25), sink=lambda u: -0.35 * u)
    T = a.seconds
    for f in range(1, N + 1, max(1, FPS // 2)):
        ang = math.radians(-60 + 35 * (f - 1) / max(1, N - 1))
        look_key(cam, f, (24 * math.cos(ang), 24 * math.sin(ang), 4.5), (0, 0, 0.6))
    cam.data.lens = 40
elif SHOT == "sink":
    sky(14, 230, 0.55, 3.0)
    ocean(wind=8, scale=0.7, rgb=(0.012, 0.04, 0.05))
    # settles level, then slips under quickly
    bob(amp=0.02, roll=0.5, period=7, base=(0, 0, -0.6),
        sink=lambda u: -(1.0 * u + 9.0 * max(0.0, u - 0.45) ** 1.6))
    look_key(cam, 1, (16, -22, 3.2), (0, 0, 0.6))
    look_key(cam, N, (13, -20, 2.4), (0, 0, -0.4))
    cam.data.lens = 38
else:  # reef
    # underwater: deep blue volume, light from above, sandy floor with ripples, ship upright on it
    bg.inputs[0].default_value = (0.005, 0.04, 0.07, 1)
    bg.inputs[1].default_value = 0.25
    vm = bpy.data.materials.new("water_volume")
    vnt = vm.node_tree
    vnt.nodes.remove(vnt.nodes["Principled BSDF"])
    vol = vnt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.1, 0.35, 0.45, 1)
    vol.inputs["Density"].default_value = 0.03
    vol.inputs["Absorption Color"].default_value = (0.2, 0.6, 0.75, 1)
    vnt.links.new(vol.outputs[0], vnt.nodes["Material Output"].inputs["Volume"])
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 6))
    vbox = bpy.context.object
    vbox.scale = (140, 140, 15)
    vbox.data.materials.append(vm)
    if a.engine == "cycles":
        S.cycles.volume_bounces = 1
        S.cycles.volume_step_rate = 4
    sand, nt, b = node_mat("sand")
    b.inputs["Base Color"].default_value = (0.2, 0.18, 0.13, 1)
    b.inputs["Roughness"].default_value = 0.95
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 3; wave.inputs["Distortion"].default_value = 6
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, -1.3))
    bpy.context.object.data.materials.append(sand)
    # scattered rocks
    rock = solid("rock", (0.15, 0.17, 0.15), 0.9)
    for k in range(40):
        x, y = random.uniform(-40, 40), random.uniform(-30, 30)
        if abs(y) < 4 and abs(x) < 17:
            continue
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(0.2, 0.9), location=(x, y, -1.3))
        r = bpy.context.object
        r.scale.z = 0.5
        r.data.materials.append(rock)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(12), 0, math.radians(30)))
    sun = bpy.context.object
    sun.data.energy = 9
    sun.data.color = (0.65, 0.92, 1.0)
    sun.data.angle = math.radians(4)
    ship_key(1, (0, 0, -0.05), (0, 0, 0))
    look_key(cam, 1, (-19, -9, 0.2), (-8, 0, 0.6))
    look_key(cam, N, (-12, -10, 2.4), (-2, 0, 1.0))
    cam.data.lens = 26

# Smooth camera motion
if cam.animation_data and cam.animation_data.action:
    pass

# ----------------------------------------------------------------- render
tmp = Path(tempfile.mkdtemp())
if a.still:
    S.frame_set(max(1, round(a.at * N)))
    S.render.filepath = a.still
    bpy.ops.render.render(write_still=True)
    print("wrote", a.still)
    sys.exit(0)

S.render.filepath = str(tmp / "f_")
S.render.image_settings.file_format = "PNG"
bpy.ops.render.render(animation=True)
out = Path(a.out).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
# Upscale to 1080x1920 (lanczos) and encode
vf = "scale=1080:1920:flags=lanczos"
if FPS < 24:  # fill in frames with motion interpolation
    vf = "minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1," + vf
subprocess.run([ffmpeg(), "-v", "error", "-y", "-framerate", str(FPS), "-i", str(tmp / "f_%04d.png"),
                "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "14", "-preset", "slow", str(out)], check=True)
shutil.rmtree(tmp)
print("wrote", out)
