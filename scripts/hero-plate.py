"""Renders the hero's film: one laminate plate, from solid to its plies, to the load, to the ply the engine names.

The plate is the home page's own stack, IM7/8552 [45/-45/0/90]s: eight unidirectional carbon plies, bottom face up, angles
counted from x to the fibres (ADR-0004). Under Nx the engine's first-ply-failure answer for this stack names ply 4 (+90°),
in transverse tension (tests/fixtures/home/response-im7-quasi-loaded.json, the same answer the scroll tour shows live). The
film shows which ply, never a number.

Run with Blender 4.2 or later:

    blender -b -P scripts/hero-plate.py -- --frames .local/hero-plate/frames

    --seconds 12 --fps 30      the loop's length and rate (the last frame leads back into the first)
    --scale 100                percent of 1920 by 1080
    --samples 128              Cycles samples per pixel, before denoising
    --only 0,90,180            render just these frames (for a look); --still 0.6 renders the one frame at that share of the loop
    --device auto|cpu|gpu      gpu uses Metal, OptiX, CUDA, HIP or oneAPI, whichever the machine offers
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

ANGLES = [45, -45, 0, 90, 90, 0, -45, 45]  # bottom face up
FAILING_PLY = 4  # the engine's answer for this stack under Nx: ply 4 (+90°), transverse tension
WIDTH, DEPTH = 1.4, 0.9  # the plate: x along the 0° fibres, y across
PLY = 0.0125  # ply thickness in scene units, about seven times true scale so the layers read
EXPLODE = 3.0  # the gap between fanned plies, in ply thicknesses
FAN = 0.1  # how far each ply slides out from the one above when fanned
SLIDE = Vector((0.62, -0.78, 0.0))  # towards the camera
AMBER = (1.0, 0.42, 0.10)


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--frames", default="frames")
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--scale", type=int, default=100)
    p.add_argument("--samples", type=int, default=128)
    p.add_argument("--only", default="")
    p.add_argument("--still", type=float, default=None)
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu"])
    return p.parse_args(argv)


# --- the loop's clock -------------------------------------------------------------------------------------------------

def smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def span(t: float, a: float, b: float) -> float:
    return min(1.0, max(0.0, (t - a) / (b - a)))


def state(t: float) -> dict:
    """What the film shows at the share `t` of the loop (0 to 1). Every part returns to where it started."""
    fan = smooth(span(t, 0.12, 0.34)) * (1 - smooth(span(t, 0.84, 0.96)))
    load = smooth(span(t, 0.44, 0.54)) * (1 - smooth(span(t, 0.78, 0.86)))
    mark = smooth(span(t, 0.56, 0.66)) * (1 - smooth(span(t, 0.78, 0.86)))
    return {"fan": fan, "load": load, "mark": mark, "turn": math.sin(2 * math.pi * t)}


# --- materials --------------------------------------------------------------------------------------------------------

def carbon(name: str, angle_deg: float):
    """Unidirectional carbon under clear resin: a dark fibre bed that reflects like brushed metal along the fibres, so its
    highlight runs across them, with fine streaks along them and a smooth coat on top."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    coords = nt.nodes.new("ShaderNodeTexCoord")
    turn = nt.nodes.new("ShaderNodeMapping")  # object coordinates turned so that x runs along this ply's fibres
    turn.inputs["Rotation"].default_value = (0, 0, -math.radians(angle_deg))
    nt.links.new(coords.outputs["Object"], turn.inputs["Vector"])

    def streaks(along: float, across: float, detail: float):
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (along, across, across)
        nt.links.new(turn.outputs["Vector"], mapping.inputs["Vector"])
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 1.0
        noise.inputs["Detail"].default_value = detail
        noise.inputs["Roughness"].default_value = 0.6
        nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        return noise

    fine = streaks(0.03, 300.0, 6.0)  # the fibres
    tows = streaks(0.012, 30.0, 2.0)  # the tows, a few millimetres wide
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.45
    nt.links.new(fine.outputs["Fac"], mix.inputs["A"])
    nt.links.new(tows.outputs["Fac"], mix.inputs["B"])

    def ranged(low: float, high: float):
        node = nt.nodes.new("ShaderNodeMapRange")
        node.inputs["From Min"].default_value = 0.3
        node.inputs["From Max"].default_value = 0.7
        node.inputs["To Min"].default_value = low
        node.inputs["To Max"].default_value = high
        nt.links.new(mix.outputs["Result"], node.inputs["Value"])
        return node

    nt.links.new(ranged(0.24, 0.42).outputs["Result"], bsdf.inputs["Roughness"])
    grey = nt.nodes.new("ShaderNodeCombineColor")
    shade = ranged(0.10, 0.24)
    for channel in ("Red", "Green", "Blue"):
        nt.links.new(shade.outputs["Result"], grey.inputs[channel])
    nt.links.new(grey.outputs["Color"], bsdf.inputs["Base Color"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    tangent = nt.nodes.new("ShaderNodeVectorRotate")  # the fibre direction
    tangent.rotation_type = "Z_AXIS"
    tangent.inputs["Vector"].default_value = (1, 0, 0)
    tangent.inputs["Angle"].default_value = math.radians(angle_deg)
    nt.links.new(tangent.outputs["Vector"], bsdf.inputs["Tangent"])
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Anisotropic"].default_value = 0.92
    bsdf.inputs["Coat Weight"].default_value = 0.55
    bsdf.inputs["Coat Roughness"].default_value = 0.05
    bsdf.inputs["Coat IOR"].default_value = 1.55
    bsdf.inputs["Emission Color"].default_value = (*AMBER, 1)
    bsdf.inputs["Emission Strength"].default_value = 0.0
    return mat, bsdf


def glow(name: str, colour):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*colour, 1)
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.0
    nt.links.new(clear.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emit.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat, mix, emit


# --- the scene --------------------------------------------------------------------------------------------------------

def make_ply(index: int, angle: float):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = f"ply-{index + 1}"
    obj.scale = (WIDTH, DEPTH, PLY)
    bpy.ops.object.transform_apply(scale=True)
    bevel = obj.modifiers.new("edge", "BEVEL")
    bevel.width = PLY * 0.16
    bevel.segments = 2
    mat, bsdf = carbon(f"carbon-{index + 1}", angle)
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    obj.modifiers.new("normals", "WEIGHTED_NORMAL")
    return obj, bsdf


def make_arrow(material):
    """A flat arrow along +x, its tail at the origin: the load per unit width, Nx."""
    length, shaft, head, head_length = 0.2, 0.012, 0.034, 0.06
    points = [(0, -shaft), (length - head_length, -shaft), (length - head_length, -head), (length, 0),
              (length - head_length, head), (length - head_length, shaft), (0, shaft)]
    mesh = bpy.data.meshes.new("arrow")
    mesh.from_pydata([(x, y, 0) for x, y in points], [], [list(range(len(points)))])
    mesh.materials.append(material)
    obj = bpy.data.objects.new("arrow", mesh)
    bpy.context.collection.objects.link(obj)
    obj.visible_shadow = False
    return obj


def area(name, location, target, size, power, colour=(1, 1, 1), spread=110.0):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    data.energy = power
    data.color = colour
    data.spread = math.radians(spread)
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    obj.visible_camera = False
    bpy.context.collection.objects.link(obj)
    return obj


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    plies = [make_ply(index, angle) for index, angle in enumerate(ANGLES)]

    arrow_mat, arrow_mix, arrow_emit = glow("load", (1.0, 1.0, 1.0))
    arrows = []  # (object, ply index, +1 or -1 end, offset across)
    for index in range(len(ANGLES)):
        for end in (1, -1):
            for across in (-0.22, 0.22):
                arrows.append((make_arrow(arrow_mat), index, end, across))

    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.0006))
    floor = bpy.context.object
    fmat = bpy.data.materials.new("floor")
    fmat.use_nodes = True
    fb = fmat.node_tree.nodes["Principled BSDF"]
    fb.inputs["Base Color"].default_value = (0.004, 0.004, 0.004, 1)
    fb.inputs["Roughness"].default_value = 0.6
    fb.inputs["Specular IOR Level"].default_value = 0.12
    floor.data.materials.append(fmat)

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    scene.world = world

    cam_data = bpy.data.cameras.new("camera")
    cam_data.lens = 50
    cam_data.shift_x = -0.16  # the plate stands right of the middle, clear of the headline
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 6.3
    cam = bpy.data.objects.new("camera", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    # The studio: a thin strip the camera sees mirrored in the resin as one soft line; a wide box overhead for the fibres'
    # sheen; a strip at the right for the near edges; a low strip in front that reaches into the fanned plies.
    centre = (0, 0, 0.05)
    eye = Vector((2.35, -2.75, 1.6))
    mirror = Vector((-eye.x, -eye.y, eye.z)).normalized()
    area("band", tuple(mirror * 4.2 + Vector((0.9, 0.5, 0.25))), centre, (3.0, 0.05), 4.0, spread=120)
    area("soft", (0.2, 0.3, 3.2), centre, (3.0, 3.0), 120)
    area("rim", (2.9, 0.9, 0.7), centre, (0.3, 2.6), 60, (0.86, 0.92, 1.0), spread=80)
    area("front", (1.2, -3.0, 0.5), centre, (2.6, 0.3), 14)
    return scene, cam, plies, arrows, arrow_mix, arrow_emit


def pose(t: float, cam, plies, arrows, arrow_mix, arrow_emit):
    s = state(t)
    gap = s["fan"] * EXPLODE * PLY
    count = len(plies)
    tops = []
    for index, (obj, bsdf) in enumerate(plies):
        slide = SLIDE * ((count - 1 - index) * FAN * s["fan"])
        obj.location = (slide.x, slide.y, index * (PLY + gap) + PLY / 2)
        tops.append(obj.location.copy())
        bsdf.inputs["Emission Strength"].default_value = 0.9 * s["mark"] if index + 1 == FAILING_PLY else 0.0
    # The load: arrows at both x ends of every ply, growing out as it goes on.
    arrow_mix.inputs["Fac"].default_value = 0.85 * s["load"]
    arrow_emit.inputs["Strength"].default_value = 1.6
    for obj, index, end, across in arrows:
        base = tops[index]
        reach = 0.03 + 0.05 * s["load"]
        obj.location = (base.x + end * (WIDTH / 2 + reach), base.y + across, base.z)
        obj.rotation_euler = (0, 0, 0 if end > 0 else math.pi)
        obj.scale = (0.4 + 0.6 * s["load"],) * 3
        obj.hide_render = s["load"] <= 0.001
    # The camera: a slow sway of a few degrees, and a step back as the plies fan out.
    height = count * PLY + (count - 1) * gap
    reach = FAN * (count - 1) * s["fan"]
    azimuth = math.atan2(-2.75, 2.35) + math.radians(5.0) * s["turn"]
    distance = 3.62 * (1 + 0.3 * s["fan"])
    look = Vector((0.05 + SLIDE.x * reach * 0.42, 0.02 + SLIDE.y * reach * 0.42, height * 0.42))
    cam.location = (look.x + distance * math.cos(azimuth), look.y + distance * math.sin(azimuth), 1.6 + height * 0.7)
    cam.rotation_euler = (look - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.focus_distance = (look - cam.location).length - 0.25


def setup_render(scene, args):
    scene.render.engine = "CYCLES"
    device = "CPU"
    if args.device != "cpu":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            (getattr(prefs, "refresh_devices", None) or prefs.get_devices)()
            found = [d for d in prefs.devices if d.type == kind]
            if found:
                for d in prefs.devices:
                    d.use = d.type == kind
                device = "GPU"
                print("rendering on", kind, [d.name for d in found])
                break
    if device == "CPU" and args.device == "gpu":
        sys.exit("no GPU device found for Cycles")
    scene.cycles.device = device
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = args.scale
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.image_settings.file_format = "PNG"


def main():
    args = parse()
    scene, cam, plies, arrows, arrow_mix, arrow_emit = build()
    setup_render(scene, args)
    os.makedirs(args.frames, exist_ok=True)
    total = round(args.seconds * args.fps)
    if args.still is not None:
        frames = [round(args.still * total) % total]
    elif args.only:
        frames = [int(value) for value in args.only.split(",")]
    else:
        frames = list(range(total))
    for frame in frames:
        path = os.path.join(args.frames, f"frame-{frame:04d}.png")
        if not args.only and args.still is None and os.path.exists(path):
            continue  # an interrupted render carries on where it stopped
        pose(frame / total, cam, plies, arrows, arrow_mix, arrow_emit)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"frame {frame} of {total}", flush=True)


main()
