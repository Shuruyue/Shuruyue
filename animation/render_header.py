"""Turn the MD trajectory into the profile header: an animated WebP (light and dark versions).

Laid out like a journal figure (panel letters, axis titles with italic symbols and units in brackets,
outward ticks, no grid, Arial):
(a) the cluster, cut in half so the inside is visible, rendered by OVITO's Tachyon ray tracer with
    ambient occlusion; atoms colored by adaptive common neighbor analysis (a-CNA, computed on the whole
    cluster before the cut). The camera makes one full turn per loop.
(b) the thermostat set point and the measured kinetic temperature against time;
(c) the a-CNA fractions (fcc, hcp, ico and their sum) against time, below the interior-atom bound.
Panels b and c are drawn up to the current frame; a faint vertical line marks it.

Every number drawn comes from the trajectory file or from OVITO's analysis of it.

Output: animation/data/<system>-{light,dark}.webp, or with --header the published profile header
assets/crystallization-{light,dark}.webp, so a test render never replaces the header by accident.

Run:  python animation/render_header.py --system cu561 --header [--frames 120] [--fps 12] [--quality 80]
      python animation/render_header.py --system cu147 --csv-only   (structure fractions only)
"""

from __future__ import annotations

import argparse
from functools import lru_cache
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
FONTS = {"": "C:/Windows/Fonts/arial.ttf", "i": "C:/Windows/Fonts/ariali.ttf",  # Arial, the usual
         "b": "C:/Windows/Fonts/arialbd.ttf"}                                 # journal-figure font

S = 2                          # output pixels per display pixel: sharp on high-DPI screens, and lossy WebP's
                               # half-resolution colour then still matches a standard screen's pixels
SS = 2                         # the chart is drawn at SS x the output size and downsampled: smooth lines
W, H = 840 * S, 280 * S        # output; displayed at 840 x 280 in the README
CLUSTER = 280 * S              # square cluster panel on the left
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


C = S * SS                     # chart canvas pixels per display pixel
T_RANGE = (200.0, 1550.0)      # temperature axis, K
F_MAX = 0.6                    # structure-fraction axis
INTERIOR = 309 / 561           # interior atoms of the Mackay icosahedron: about the most that can be crystalline


@lru_cache(maxsize=None)
def font(size: float, style: str = "") -> ImageFont.FreeTypeFont:
    """Arial at `size` display pixels, for the chart canvas; style "" regular, "i" italic, "b" bold."""
    return ImageFont.truetype(FONTS[style], round(size * C))


def part_font(size: float, style: str) -> ImageFont.FreeTypeFont:
    return font(size * 0.72) if style == "sub" else font(size, style)


def text_parts(draw: ImageDraw.ImageDraw, xy, parts, fill, size: float, anchor: str = "left") -> None:
    """Draw parts = [(text, style), ...] on one baseline. Styles: "" roman, "i" italic (quantity symbols),
    "b" bold, "sub" subscript. xy is on the baseline, at the left end, the right end or the centre."""
    width = sum(draw.textlength(text, font=part_font(size, style)) for text, style in parts)
    x, y = xy
    x -= {"left": 0.0, "right": width, "center": width / 2}[anchor]
    for text, style in parts:
        f = part_font(size, style)
        draw.text((x, y + (0.22 * size * C if style == "sub" else 0)), text, font=f, fill=fill, anchor="ls")
        x += draw.textlength(text, font=f)


def vertical_text(canvas: Image.Image, center, parts, fill, size: float) -> None:
    """An axis title turned 90 degrees (read bottom to top), centred on `center` in canvas pixels."""
    probe = ImageDraw.Draw(canvas)
    width = sum(probe.textlength(text, font=part_font(size, style)) for text, style in parts)
    # transparent layer in the text colour, so the antialiased edges blend without a dark fringe
    layer = Image.new("RGBA", (round(width) + 4, round(1.6 * size * C)), tuple(fill) + (0,))
    text_parts(ImageDraw.Draw(layer), (2, round(1.15 * size * C)), parts, tuple(fill) + (255,), size)
    layer = layer.rotate(90, expand=True)
    canvas.paste(layer, (round(center[0] - layer.width / 2), round(center[1] - layer.height / 2)), layer)


def compose(theme: dict, cluster_png: Path, k: int, n_anim: int, idx: np.ndarray, md: dict,
            fractions: np.ndarray, n_atoms: int) -> Image.Image:
    """One animation frame, laid out like a journal figure: (a) the snapshot, (b) temperature, (c) structure.
    Layout numbers are display pixels (the README shows the card at 840 x 280)."""
    canvas = Image.new("RGB", (W * SS, H * SS), theme["page"])
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([0, 0, W * SS - 1, H * SS - 1], radius=10 * C, outline=theme["border"], width=C)
    ink, muted = theme["text"], theme["muted"]
    xy = lambda x, y: (x * C, y * C)

    def hline(xa, xb, y, fill):  # 1 display pixel thick, on the display pixel grid: crisp after scaling
        y = round(y)
        d.rectangle([round(xa) * C, y * C, round(xb) * C - 1, (y + 1) * C - 1], fill=fill)

    def vline(x, ya, yb, fill):
        x = round(x)
        d.rectangle([x * C, round(ya) * C, (x + 1) * C - 1, round(yb) * C - 1], fill=fill)

    def panel_label(x, y, letter):
        d.text(xy(x, y), letter, font=font(13, "b"), fill=ink, anchor="lt")

    def knockout(xa, ya, xb, yb):  # page-coloured patch: the moving cursor line breaks behind a label
        d.rectangle([xa * C, ya * C, xb * C, yb * C], fill=theme["page"])

    # (a) the cluster, pasted first so the labels sit on top (nearest-neighbour upscaling followed by the
    # final box downscaling returns the rendered pixels unchanged)
    cluster = Image.open(cluster_png).convert("RGBA")
    fade = min(1.0, (k + 1) / FADE, (n_anim - k) / FADE)
    if fade < 1.0:
        cluster.putalpha(cluster.getchannel("A").point(lambda a: int(a * fade)))
    cluster = cluster.resize((cluster.width * SS, cluster.height * SS), Image.NEAREST)
    canvas.paste(cluster, (0, 0), cluster)
    panel_label(12, 10, "a")
    text_parts(d, xy(CLUSTER // S - 12, 21), [("Cu", ""), (str(n_atoms), "sub")], ink, 11, anchor="right")
    for j, (_, name, color) in enumerate(STRUCTURES):  # colour key of the snapshot, bottom-left corner
        y = 232 + 12 * j
        d.ellipse([(18 - 3.5) * C, (y - 7.5) * C, (18 + 3.5) * C, (y - 0.5) * C],
                  fill=tuple(int(255 * c) for c in color), outline=muted if name == "other" else None,
                  width=C // 2)
        d.text(xy(26, y), name, font=font(10), fill=ink, anchor="ls")

    t, temp_target, temp_kin = md["time_ps"], md["target_K"], md["kinetic_K"]
    i_now = idx[k]
    x0, x1 = 352, 820
    to_x = lambda tt: x0 + (x1 - x0) * tt / t[-1]
    cx = to_x(t[i_now])

    def axes(ya, yb, yticks, xlabels):
        """Left and bottom axis lines with outward ticks; time ticks every 100 ps."""
        vline(x0, ya, yb + 1, ink)
        hline(x0, x1 + 1, yb, ink)
        for y, text in yticks:
            hline(x0 - 3, x0, y, ink)
            d.text(xy(x0 - 6, y), text, font=font(10), fill=ink, anchor="rm")
        for tick in range(0, int(t[-1]) + 1, 100):
            vline(to_x(tick), yb + 1, yb + 4, ink)
            if xlabels:
                d.text(xy(to_x(tick), yb + 6), f"{tick}", font=font(10), fill=ink, anchor="mt")

    # (b) thermostat set point (the whole schedule, drawn up to now) and the measured kinetic temperature
    yb0, yb1 = 30, 112
    to_yt = lambda temp: yb1 - (yb1 - yb0) * (temp - T_RANGE[0]) / (T_RANGE[1] - T_RANGE[0])
    panel_label(300, 10, "b")
    text_parts(d, xy(x1, 19), [("t", "i"), (f" = {t[i_now]:.0f} ps", ""), ("      T", "i"), ("set", "sub"),
                               (f" = {temp_target[i_now]:.0f} K", "")], ink, 11, anchor="right")
    vline(cx, yb0, yb1, theme["grid"])
    axes(yb0, yb1, [(to_yt(v), f"{v}") for v in (300, 900, 1500)], xlabels=False)
    vertical_text(canvas, xy(312, (yb0 + yb1) / 2), [("T", "i"), (" (K)", "")], ink, 10.5)
    kin_color = tuple((g + m) // 2 for g, m in zip(theme["grid"], muted))
    now = slice(0, i_now + 1)
    kin = [xy(to_x(a), to_yt(b)) for a, b in zip(t[now], temp_kin[now])]
    pts = [xy(to_x(a), to_yt(b)) for a, b in zip(t, temp_target)]
    if len(kin) > 1:
        d.line(kin, fill=kin_color, width=C)
    d.line(pts[i_now:], fill=muted, width=C, joint="curve")
    if i_now > 0:
        d.line(pts[: i_now + 1], fill=theme["line"], width=round(1.5 * C), joint="curve")
    px, py = pts[i_now]
    d.ellipse([px - 3.5 * C, py - 3.5 * C, px + 3.5 * C, py + 3.5 * C], fill=theme["line"])
    key_b = (("set point", theme["line"], 1.5), ("kinetic", kin_color, 1.0))
    widest = max(d.textlength(name, font=font(10)) for name, _, _ in key_b) / C
    knockout(x1 - widest - 25, 33, x1 + 1, 60)
    for j, (name, color, width) in enumerate(key_b):
        y = 40 + 13 * j
        tw = d.textlength(name, font=font(10)) / C
        d.text(xy(x1, y), name, font=font(10), fill=ink, anchor="rm")
        d.line([xy(x1 - tw - 22, y), xy(x1 - tw - 6, y)], fill=color, width=round(width * C))

    # (c) a-CNA fractions; "other" is the rest. Dashed: the interior atoms, about the crystalline maximum
    yc0, yc1 = 146, 236
    to_yf = lambda f: yc1 - (yc1 - yc0) * f / F_MAX
    panel_label(300, 132, "c")
    vline(cx, yc0, yc1, theme["grid"])
    axes(yc0, yc1, [(to_yf(v), f"{v:.1f}") for v in (0.0, 0.2, 0.4, 0.6)], xlabels=True)
    vertical_text(canvas, xy(312, (yc0 + yc1) / 2), [("Fraction", "")], ink, 10.5)
    text_parts(d, xy((x0 + x1) / 2, 267), [("t", "i"), (" (ps)", "")], ink, 10.5, anchor="center")
    y_int = to_yf(INTERIOR)
    for xa in range(x0 + 2, x1, 6):
        hline(xa, min(xa + 3, x1), y_int, muted)
    bound = "interior atoms (upper bound)"
    knockout(x1 - d.textlength(bound, font=font(9)) / C - 3, y_int - 13, x1 + 1, round(y_int) - 0.5)
    d.text(xy(x1, y_int - 2), bound, font=font(9), fill=muted, anchor="rb")
    rgb = [tuple(int(255 * c) for c in color) for _, _, color in STRUCTURES]
    series = [(fractions[:, 2], rgb[2], 1.0, "ico"), (fractions[:, 0], rgb[0], 1.0, "fcc"),
              (fractions[:, 1], rgb[1], 1.0, "hcp"), (fractions[:, :3].sum(axis=1), ink, 1.5, "fcc + hcp + ico")]
    for values, color, width, _ in series:
        line = [xy(to_x(a), to_yf(b)) for a, b in zip(t[now], values[now])]
        if len(line) > 1:
            d.line(line, fill=color, width=round(width * C), joint="curve")
    lx = to_x(130)  # legend in the empty stretch of the liquid, where every fraction is ~0
    key_c = list(reversed(series))
    widest = max(d.textlength(name, font=font(10)) for *_, name in key_c) / C
    knockout(lx - 3, 161, lx + 24 + widest, 172 + 12 * (len(key_c) - 1) + 4)
    for j, (_, color, width, name) in enumerate(key_c):
        y = 172 + 12 * j
        d.line([xy(lx, y - 3.5), xy(lx + 16, y - 3.5)], fill=color, width=round(width * C))
        d.text(xy(lx + 21, y), name, font=font(10), fill=ink, anchor="ls")

    return canvas.resize((W, H), Image.BOX)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", default=None,
                        help="cu147, cu561 or cu561_slowfreeze (default: the largest cu<N> run with the fast schedule)")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument("--skip-render", action="store_true", help="reuse rendered cluster PNGs")
    parser.add_argument("--csv-only", action="store_true", help="write the structure fractions and stop")
    parser.add_argument("--header", action="store_true",
                        help="write the profile header in assets/ (default: animation/data/<system>-*.webp)")
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
               np.column_stack([md["time_ps"], md["target_K"], md["kinetic_K"], fractions]), delimiter=",",
               fmt="%.4f", header="time_ps,target_K,kinetic_K,fcc,hcp,ico,other", comments="")
    print("a-CNA fractions at the end:", dict(zip(("fcc", "hcp", "ico", "other"), fractions[-1].round(3))))
    if args.csv_only:
        return

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
        imgs = [compose(theme, png_dir / f"{k:04d}.png", k, n_anim, idx, md, fractions, n_atoms)
                for k in range(n_anim)]
        out = ASSETS / f"crystallization-{name}.webp" if args.header else DATA / f"{args.system}-{name}.webp"
        imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=duration, loop=0,
                     quality=args.quality, method=6, lossless=False, allow_mixed=True)
        imgs[n_anim // 2].save(DATA / f"preview-{args.system}-{name}.png")
        print(f"{out.name}: {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
