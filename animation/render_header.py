"""Turn the MD trajectory into the profile header: an animated WebP (light and dark versions).

Left: the cluster, cut in half so the inside is visible, rendered by OVITO's Tachyon ray tracer with
ambient occlusion; atoms colored by adaptive common neighbor analysis (a-CNA, computed on the whole
cluster before the cut). The camera makes one full turn per loop.
Right: the temperature schedule and the a-CNA structure fractions of the whole run, with a cursor
that follows the animation.

Every number drawn comes from the trajectory file or from OVITO's analysis of it.

Run:  python animation/render_header.py [--system cu561] [--frames 160] [--fps 16]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.io import write
from ovito.io import import_file
from ovito.modifiers import CommonNeighborAnalysisModifier, ComputePropertyModifier, SliceModifier
from ovito.vis import TachyonRenderer, Viewport
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ASSETS = HERE.parent / "assets"
FONT = "C:/Windows/Fonts/CascadiaMono.ttf"  # Cascadia Mono, SIL Open Font License

S = 1.5                        # pixel scale (> 1 keeps it sharp on high-DPI screens)
W, H = int(840 * S), int(280 * S)   # canvas; displayed at 840 x 280 in the README
CLUSTER = int(280 * S)         # square cluster panel on the left
RADIUS = 1.2                   # sphere radius, Angstrom (Cu nearest-neighbour distance ~2.55)
CAMERA_DIR = np.array([0.0, 1.0, -0.28])
CAMERA_DIR /= np.linalg.norm(CAMERA_DIR)
FADE = 5                       # frames of fade-out / fade-in at the loop seam

CNA = CommonNeighborAnalysisModifier.Type
STRUCTURES = [  # (a-CNA type, label, RGB 0-1); same colors in the render and the chart
    (CNA.FCC, "fcc", (0.30, 0.76, 0.42)),
    (CNA.HCP, "hcp", (0.90, 0.35, 0.33)),
    (CNA.ICO, "ico", (0.90, 0.71, 0.26)),
    (CNA.OTHER, "other", (0.84, 0.84, 0.86)),
]
# Opaque card on GitHub's page colour, framed like the stats and quote cards. (A transparent WebP was
# twice the size: the alpha plane cost as much as the picture.)
THEMES = {
    "light": {"page": (255, 255, 255), "border": (208, 215, 222), "text": (31, 35, 40), "muted": (101, 109, 118),
              "grid": (208, 215, 222), "line": (9, 105, 218)},
    "dark": {"page": (13, 17, 23), "border": (48, 54, 61), "text": (230, 237, 243), "muted": (139, 148, 158),
             "grid": (48, 54, 61), "line": (88, 166, 255)},
}


def kabsch_align(frames: np.ndarray) -> np.ndarray:
    """Center every frame and remove rigid rotation relative to the previous frame."""
    out = frames - frames.mean(axis=1, keepdims=True)
    for k in range(1, len(out)):
        h = out[k].T @ out[k - 1]
        u, _, vt = np.linalg.svd(h)
        d = np.sign(np.linalg.det(u @ vt))
        rot = u @ np.diag([1.0, 1.0, d]) @ vt
        out[k] = out[k] @ rot
    return out


def rotate_z(points: np.ndarray, angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return points @ np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]).T


def write_xyz(path: Path, frames: np.ndarray) -> None:
    n = frames.shape[1]
    write(path, [Atoms(f"Cu{n}", positions=f) for f in frames])


def cna_modifier() -> CommonNeighborAnalysisModifier:
    mod = CommonNeighborAnalysisModifier(mode=CommonNeighborAnalysisModifier.Mode.AdaptiveCutoff)
    for kind, _, color in STRUCTURES:
        mod.structures[kind].color = color
    # a-CNA also finds bcc (at most 11 atoms in any frame of the Cu561 run); the chart counts them as "other",
    # so color them alike
    mod.structures[CNA.BCC].color = STRUCTURES[-1][2]
    return mod


def structure_fractions(xyz: Path) -> np.ndarray:
    """a-CNA fractions (fcc, hcp, ico, other) for every frame of the full trajectory."""
    pipeline = import_file(str(xyz))
    pipeline.modifiers.append(cna_modifier())
    fractions = []
    for frame in range(pipeline.source.num_frames):
        types = np.asarray(pipeline.compute(frame).particles["Structure Type"])
        fractions.append([np.mean(types == kind) for kind, _, _ in STRUCTURES[:3]])
    f = np.array(fractions)
    return np.column_stack([f, 1.0 - f.sum(axis=1)])


def render_cluster(xyz: Path, n_frames: int, extent: float, out_dir: Path) -> None:
    pipeline = import_file(str(xyz))
    pipeline.modifiers.append(cna_modifier())
    pipeline.modifiers.append(ComputePropertyModifier(output_property="Radius", expressions=[str(RADIUS)]))
    # delete the half of the cluster that faces the camera, so the cut face shows the inside
    pipeline.modifiers.append(SliceModifier(normal=tuple(-CAMERA_DIR), distance=0.0))
    pipeline.add_to_scene()
    distance = 4.2 * extent
    # OVITO's fov is the full opening angle; leave a 10 % margin around the largest extent
    vp = Viewport(type=Viewport.Type.Perspective, camera_pos=tuple(-CAMERA_DIR * distance),
                  camera_dir=tuple(CAMERA_DIR), fov=2 * np.arctan(1.1 * extent / distance))
    renderer = TachyonRenderer(ambient_occlusion=True, ambient_occlusion_brightness=0.85,
                               ambient_occlusion_samples=24, shadows=False, antialiasing_samples=16,
                               direct_light_intensity=0.95)
    out_dir.mkdir(parents=True, exist_ok=True)
    for k in range(n_frames):
        vp.render_image(size=(CLUSTER, CLUSTER), frame=k, filename=str(out_dir / f"{k:04d}.png"),
                        alpha=True, renderer=renderer)
        if k % 20 == 0:
            print(f"  rendered {k}/{n_frames}", flush=True)
    pipeline.remove_from_scene()


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, round(size * S))


def draw_text_sub(draw: ImageDraw.ImageDraw, xy, parts, fill, size: int) -> None:
    """Draw text where parts = [(text, is_subscript), ...]."""
    x, y = xy
    for text, sub in parts:
        f = font(int(size * 0.72)) if sub else font(size)
        dy = int(size * 0.42 * S) if sub else 0
        draw.text((x, y + dy), text, font=f, fill=fill)
        x += draw.textlength(text, font=f)


def compose(theme: dict, cluster_png: Path, k: int, n_anim: int, idx: np.ndarray, md: dict,
            fractions: np.ndarray, n_atoms: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), theme["page"] + (255,))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, W - 1, H - 1], radius=round(10 * S),
                                          outline=theme["border"], width=1)
    cluster = Image.open(cluster_png).convert("RGBA")
    fade = min(1.0, (k + 1) / FADE, (n_anim - k) / FADE)
    if fade < 1.0:
        alpha = cluster.getchannel("A").point(lambda a: int(a * fade))
        cluster.putalpha(alpha)
    img.alpha_composite(cluster, (0, 0))

    d = ImageDraw.Draw(img)
    t, temp_target, temp_kin = md["time_ps"], md["target_K"], md["kinetic_K"]
    i_now = idx[k]
    x0, x1 = 316 * S, 828 * S
    to_x = lambda tt: x0 + (x1 - x0) * tt / t[-1]

    draw_text_sub(d, (x0, 16 * S), [("Cu", False), (str(n_atoms), True),
                                     (" nanocluster: melt, then recrystallize", False)], theme["text"], 13)
    d.text((x1, 18 * S), f"t = {t[i_now]:.0f} ps   T = {temp_target[i_now]:.0f} K",
           font=font(11), fill=theme["muted"], anchor="ra")

    # temperature panel
    ty0, ty1 = 58 * S, 124 * S
    to_yt = lambda temp: ty1 - (ty1 - ty0) * (temp - 0.0) / 1500.0
    for temp in (300, 900, 1500):
        d.line([(x0, to_yt(temp)), (x1, to_yt(temp))], fill=theme["grid"], width=1)
        d.text((x0 - 4 * S, to_yt(temp)), f"{temp}", font=font(9), fill=theme["muted"], anchor="rm")
    d.text((x0 - 4 * S, ty0 - 12 * S), "T / K", font=font(9), fill=theme["muted"], anchor="rm")
    pts_kin = [(to_x(a), to_yt(b)) for a, b in zip(t, temp_kin)]
    d.line(pts_kin, fill=theme["grid"], width=round(S))
    pts = [(to_x(a), to_yt(b)) for a, b in zip(t, temp_target)]
    d.line(pts[: i_now + 1], fill=theme["line"], width=round(2 * S))
    d.line(pts[i_now:], fill=theme["muted"], width=round(S))
    cx, cy = pts[i_now]
    d.ellipse([cx - 4 * S, cy - 4 * S, cx + 4 * S, cy + 4 * S], fill=theme["line"])

    # structure-fraction panel (stacked areas, revealed up to the cursor)
    fy0, fy1 = 146 * S, 238 * S
    to_yf = lambda f: fy1 - (fy1 - fy0) * f
    d.text((x0 - 4 * S, fy0 - 12 * S), "a-CNA", font=font(9), fill=theme["muted"], anchor="rm")
    for f in (0.0, 0.5, 1.0):
        d.line([(x0, to_yf(f)), (x1, to_yf(f))], fill=theme["grid"], width=1)
        d.text((x0 - 4 * S, to_yf(f)), f"{f:.1f}", font=font(9), fill=theme["muted"], anchor="rm")
    cum = np.cumsum(fractions, axis=1)
    lower = np.zeros(len(t))
    for j, (_, _, color) in enumerate(STRUCTURES):
        upper = cum[:, j]
        rgb = tuple(int(255 * c) for c in color)
        sl = slice(0, i_now + 1)
        poly = [(to_x(a), to_yf(b)) for a, b in zip(t[sl], upper[sl])]
        poly += [(to_x(a), to_yf(b)) for a, b in zip(t[sl][::-1], lower[sl][::-1])]
        if len(poly) >= 3:
            d.polygon(poly, fill=rgb + (235,))
        lower = upper
    d.line([(cx, fy0), (cx, fy1)], fill=theme["text"], width=round(S))
    for tick in range(0, int(t[-1]) + 1, 100):
        d.text((to_x(tick), fy1 + 4 * S), f"{tick}", font=font(9), fill=theme["muted"], anchor="mt")
    d.text((x1, fy1 + 4 * S), "ps", font=font(9), fill=theme["muted"], anchor="rt")

    # legend with the current fractions
    lx = x0
    for j, (_, label, color) in enumerate(STRUCTURES):
        rgb = tuple(int(255 * c) for c in color)
        d.rectangle([lx, 262 * S, lx + 9 * S, 271 * S], fill=rgb)
        text = f"{label} {100 * fractions[i_now, j]:4.1f}%"
        d.text((lx + 13 * S, 266 * S), text, font=font(10), fill=theme["text"], anchor="lm")
        lx += 128 * S
    return img


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", default=None,
                        help="cu147, cu561 or cu561_slowfreeze (default: the largest cu<N> run with the fast schedule)")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--quality", type=int, default=60)
    parser.add_argument("--skip-render", action="store_true", help="reuse rendered cluster PNGs")
    args = parser.parse_args()

    if args.system is None:
        found = sorted((p for p in DATA.glob("cu*_md.npz") if p.stem.count("_") == 1),
                       key=lambda p: int(p.stem[2:].split("_")[0]))
        args.system = found[-1].stem.replace("_md", "")
    md = dict(np.load(DATA / f"{args.system}_md.npz"))
    frames = kabsch_align(md["positions"].astype(np.float64))
    n_atoms = frames.shape[1]
    print(f"{args.system}: {len(frames)} saved frames, {n_atoms} atoms")

    full_xyz = DATA / f"{args.system}_all.xyz"
    write_xyz(full_xyz, frames)
    fractions = structure_fractions(full_xyz)
    np.savetxt(DATA / f"{args.system}_cna_fractions.csv",
               np.column_stack([md["time_ps"], md["target_K"], fractions]), delimiter=",", fmt="%.4f",
               header="time_ps,target_K,fcc,hcp,ico,other", comments="")
    print("a-CNA fractions at the end:", dict(zip(("fcc", "hcp", "ico", "other"), fractions[-1].round(3))))

    n_anim = args.frames
    idx = np.linspace(0, len(frames) - 1, n_anim).round().astype(int)
    angles = 2 * np.pi * np.arange(n_anim) / n_anim
    anim = np.array([rotate_z(frames[i], a) for i, a in zip(idx, angles)])
    # framing: 99.5th percentile of the atoms' distance from the centre over the whole run, so a
    # single atom that wanders off in the liquid does not shrink the picture
    extent = float(np.percentile(np.linalg.norm(frames, axis=2), 99.5)) + RADIUS
    png_dir = DATA / f"{args.system}_frames"
    if not args.skip_render:
        anim_xyz = DATA / f"{args.system}_anim.xyz"
        write_xyz(anim_xyz, anim)
        render_cluster(anim_xyz, n_anim, extent, png_dir)

    ASSETS.mkdir(exist_ok=True)
    duration = int(round(1000 / args.fps))
    for name, theme in THEMES.items():
        imgs = [compose(theme, png_dir / f"{k:04d}.png", k, n_anim, idx, md, fractions, n_atoms).convert("RGB")
                for k in range(n_anim)]
        out = ASSETS / f"crystallization-{name}.webp"
        imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=duration, loop=0,
                     quality=args.quality, method=6, lossless=False, minimize_size=True, allow_mixed=True)
        imgs[n_anim // 2].save(DATA / f"preview-{name}.png")
        print(f"{out.name}: {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
