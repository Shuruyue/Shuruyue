# animation

The header of the profile is a molecular dynamics simulation, not a drawing: a copper nanocluster is
melted and then cooled until it crystallizes again.

| Step | Script | Output |
|---|---|---|
| 1. Simulate | `crystallization_md.py --shells 6` | `data/cu561_md.npz` (positions, time, temperatures) |
| 2. Analyse and render | `render_header.py` | `data/cu561_cna_fractions.csv`, `../assets/crystallization-{light,dark}.webp` |

## Simulation

| Setting | Value |
|---|---|
| System | Cu<sub>561</sub>, started as a Mackay icosahedron (`ase.cluster.Icosahedron`, 6 shells), in vacuum |
| Potential | effective medium theory, EMT (Jacobsen, Stoltze & Nørskov 1996), as shipped with ASE |
| Thermostat | Langevin, friction 0.02 fs<sup>-1</sup>, centre of mass fixed with `FixCom` |
| Time step | 5 fs; a frame is saved every 100 steps (0.5 ps) |
| Schedule | 300 K for 20 ps → heat to 1400 K over 60 ps → hold 20 ps → cool to 300 K over 400 ps (2.75 K/ps) → hold 30 ps |
| Seed | 7 (velocities and Langevin noise) |

## Analysis and rendering

- Structure: adaptive common neighbor analysis (a-CNA) in OVITO, on the whole cluster, every saved frame.
  Colors: fcc green, hcp red, icosahedral yellow, other grey.
- Picture: each frame is centred and its rigid rotation relative to the previous frame removed (Kabsch);
  the cluster is then turned once around the vertical axis per loop, cut in half facing the camera so the
  inside shows, and ray traced with OVITO's Tachyon renderer (ambient occlusion).
- The chart next to it is drawn from the same files: the temperature schedule (kinetic temperature in grey)
  and the a-CNA fractions up to the current frame.

## Results

*Pending: the Cu<sub>561</sub> run is still computing. Melting and freezing temperatures read from the
a-CNA fractions, and the final structure, go here.*

## Differences from standard practice

- **Cooling rate.** 2.75 × 10<sup>12</sup> K/s, about ten orders of magnitude faster than any experiment
  and typical of MD. Fast cooling favours defects and icosahedral or decahedral motifs, so the final structure
  is one possible outcome, not the equilibrium one.
- **One trajectory.** A single run with one seed; melting and freezing temperatures from it have no error
  bars, and supercooling depends on the seed and the rate.
- **Potential.** EMT is a fast, approximate many-body potential; its melting point and surface energies differ
  from experiment and from density functional theory.
- **Surface atoms.** a-CNA labels atoms by their full neighbour shell, so surface atoms are "other" even in a
  perfect crystal; about 45 % of Cu<sub>561</sub> sits on the surface.
- **Presentation.** The camera turn, the cut and the even spacing of the shown frames in time are for display
  only. The animation shows a subset of the saved frames, with a short fade at the loop.

## Rebuild

```bash
pip install -r requirements.txt
python animation/crystallization_md.py --shells 6   # about 3 h on one CPU core
python animation/render_header.py                   # about 15 min; uses all cores
```

`render_header.py` uses Cascadia Mono (SIL Open Font License) from the Windows fonts folder; change `FONT` on
other systems.
