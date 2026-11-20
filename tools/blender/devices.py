"""Report which render engines and GPU devices this Blender can use.

Run: blender -b --factory-startup -P tools/blender/devices.py   (setup.py does this for you)"""
import bpy

engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
print("BLENDER", bpy.app.version_string)
print("ENGINES", ", ".join(engines))
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    found = False
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d.name for d in prefs.devices if d.type == kind]
        if gpus:
            found = True
            print(f"CYCLES_GPU {kind}: {', '.join(gpus)}")
    if not found:
        print("CYCLES_GPU none (Cycles will use the CPU; EEVEE still uses the GPU)")
except Exception as e:  # bpy module builds without the Cycles add-on prefs
    print("CYCLES_GPU unknown:", e)
