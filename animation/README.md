# animation

The header of the profile is a molecular dynamics simulation, not a drawing: a copper nanocluster is
melted and then cooled until it crystallizes again.

| Step | Script | Output |
|---|---|---|
| 1. Simulate | `crystallization_md.py --shells 6` | `data/cu561_md.npz` (positions, time, temperatures; not committed, 6 MB) |
| 2. Analyse and render | `render_header.py` | `data/cu561_cna_fractions.csv`, `../assets/crystallization-{light,dark}.webp` |

## Simulation

| Setting | Value |
|---|---|
| System | Cu<sub>561</sub>, started as a Mackay icosahedron (`ase.cluster.Icosahedron`, 6 shells), in vacuum |
| Potential | effective medium theory, EMT (Jacobsen, Stoltze & Nørskov 1996), as shipped with ASE |
| Thermostat | Langevin, friction 0.02 fs<sup>-1</sup>, centre of mass fixed with `FixCom` |
| Time step | 5 fs; a frame is saved every 100 steps (0.5 ps) |
| Schedule (`--schedule fast`, used for the header) | 300 K for 20 ps → heat to 1400 K over 60 ps (18 K/ps) → hold 20 ps → cool to 300 K over 400 ps (2.75 K/ps) → hold 30 ps |
| Alternative (`--schedule slow-freeze`) | same heating; cool at 4 K/ps to 1000 K, 1 K/ps to 600 K, 3 K/ps to 300 K; writes `data/cu561_slowfreeze_md.npz` |
| Seed | 7 (velocities and Langevin noise) |

## Analysis and rendering

- Structure: adaptive common neighbor analysis (a-CNA) in OVITO, on the whole cluster, every saved frame.
  Colors: fcc green, hcp red, icosahedral yellow, other grey. bcc, which a-CNA assigns to at most 11 atoms
  in any frame (1 on average), is counted and colored as other.
- Picture: each frame is centred and its rigid rotation relative to the previous frame removed (Kabsch);
  the cluster is then turned once around the vertical axis per loop, cut in half facing the camera so the
  inside shows, and ray traced with OVITO's Tachyon renderer (ambient occlusion).
- The chart next to it is drawn from the same files: the temperature schedule (kinetic temperature in grey)
  and the a-CNA fractions up to the current frame.

## Results

Run shown: `--shells 6 --schedule fast`. All numbers come from `data/cu561_cna_fractions.csv`;
"crystalline" means fcc + hcp + icosahedral.

| a-CNA fraction | fcc | hcp | icosahedral | other | crystalline |
|---|---|---|---|---|---|
| Start, 300 K (mean over 0–20 ps) | 14.3 % | 32.1 % | 0.2 % (1 atom) | 53.5 % | 46.5 % |
| End, 300 K (mean over 500–530 ps) | 12.5 % | 23.5 % | 0.2 % (1 atom) | 63.8 % | 36.2 % |

- **Melting** (heating at 18 K/ps). The crystalline fraction falls below 90 % of its start value at 667 K
  and below 1 % at 1262 K. During the hold at 1400 K it never exceeds 0.2 %.
- **Freezing** (cooling at 2.75 K/ps). The crystalline fraction passes 1 % at 750 K, stays above 5 % from
  706 K and reaches half of its final value at 605 K. Melting and freezing are about 500 K apart: the
  heated crystal overshoots and the cooled liquid supercools, and both gaps depend on the rates.
- **Final structure.** A twinned crystal, not the starting icosahedron. In an fcc metal, hcp atoms mark twin
  boundaries and stacking faults, and they still make up two thirds of the crystalline atoms. The
  icosahedral atom (one, in some frames two) sits about 8 Å from the centre of a cluster about 12.7 Å in radius; in the starting Mackay
  icosahedron it is the central atom.
- **Why Cu<sub>561</sub>.** A test with Cu<sub>147</sub> and the same schedule ended with 0.5 % crystalline
  atoms (21 % at the start): at that size and rate it froze into a disordered cluster
  (`data/cu147_cna_fractions.csv`).

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
python animation/crystallization_md.py --shells 6   # about 3 h on one CPU core (i5-13400)
python animation/render_header.py                   # about 15 min; uses all cores
```

`render_header.py` uses Cascadia Mono (SIL Open Font License) from the Windows fonts folder; change `FONT` on
other systems.
