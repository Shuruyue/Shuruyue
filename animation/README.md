# animation

The header of the profile is a molecular dynamics simulation, not a drawing: a copper nanocluster is
melted and then cooled until it crystallizes again.

| Step | Script | Output |
|---|---|---|
| 1. Simulate | `crystallization_md.py --shells 6` | `data/cu561_md.npz` (positions, time, temperatures; not committed, 6 MB) |
| 2. Analyse and render | `render_header.py --system cu561` | `data/cu561_cna_fractions.csv`, `../assets/crystallization-{light,dark}.webp` |

## Simulation

| Setting | Value |
|---|---|
| System | Cu<sub>561</sub>, started as a Mackay icosahedron (`ase.cluster.Icosahedron`, 6 shells), in vacuum |
| Potential | effective medium theory, EMT (Jacobsen, Stoltze & Nørskov 1996), as shipped with ASE |
| Thermostat | Langevin, friction 0.02 fs<sup>-1</sup>, centre of mass fixed with `FixCom` |
| Time step | 5 fs; a frame is saved every 100 steps (0.5 ps). Checked in a 2-ps constant-energy run of the 1400 K liquid: total energy drifts 0.011 meV/atom/ps (0.000 at 2 fs), negligible next to the thermostat |
| Schedule (`--schedule fast`, used for the header) | 300 K for 20 ps → heat to 1400 K over 60 ps (18 K/ps) → hold 20 ps → cool to 300 K over 400 ps (2.75 K/ps) → hold 30 ps |
| Alternative (`--schedule slow-freeze`) | same heating; cool at 4 K/ps to 1000 K, 1 K/ps to 600 K, 3 K/ps to 300 K; writes `data/cu561_slowfreeze_md.npz` (result below) |
| Seed | 7 (velocities and Langevin noise) |

## Analysis and rendering

- Structure: adaptive common neighbor analysis (a-CNA) in OVITO, on the whole cluster, every saved frame.
  Colors: fcc green, hcp red, icosahedral yellow, other grey. bcc, which a-CNA assigns to at most 11 atoms
  in any frame (1 on average), is counted and colored as other.
- Picture: each frame is centred and its rigid rotation relative to the previous frame removed (Kabsch);
  the cluster is then turned once around the vertical axis per loop, cut in half facing the camera so the
  inside shows, and ray traced with OVITO's Tachyon renderer (ambient occlusion).
- The chart next to it is drawn from the same files: the thermostat set point (blue, read out as
  T<sub>set</sub>) with the cluster's instantaneous kinetic temperature behind it (grey), and the a-CNA
  fractions up to the current frame.
- Output: 120 frames at 12 frames/s, 1680 × 560 pixels shown at 840 × 280. Twice the display size keeps it
  sharp on high-density screens, and lossy WebP (quality 80) stores colour at half resolution, which then
  still matches a standard screen's pixels. The chart is drawn at twice that again and scaled down.

## Results

Run shown: `--shells 6 --schedule fast`. All numbers come from `data/cu561_cna_fractions.csv` (time, set
point, kinetic temperature, fractions). "Crystalline" means fcc + hcp + icosahedral. Temperatures are set
points: averaged over 5 ps, the kinetic temperature stays within 10 K of the set point on average in every
stage, and within 18 K while the cluster freezes, so the thermostat absorbs the latent heat as it is released.

| a-CNA fraction | fcc | hcp | icosahedral | other | crystalline |
|---|---|---|---|---|---|
| Start, 300 K (mean over 0–20 ps) | 14.3 % | 32.1 % | 0.2 % (1 atom) | 53.5 % | 46.5 % |
| End, 300 K (mean over 500–530 ps) | 12.5 % | 23.5 % | 0.2 % (1 atom) | 63.8 % | 36.2 % |

Only interior atoms can count as crystalline, because a-CNA needs a full shell of neighbours. In the perfect
starting icosahedron the 300 "other" atoms are the 252 surface atoms plus the 48 on its twelve five-fold
axes, so its 309 interior atoms (55 %) are about the most that can be crystalline.

- **Melting** (heating at 18 K/ps). The crystalline fraction falls to half its start value at 997 K and below
  1 % at 1262 K. During the hold at 1400 K it never exceeds 0.2 %.
- **Freezing** (cooling at 2.75 K/ps). It passes 1 % at 750 K, reaches half its final value at 605 K and
  90 % at 428 K.
- **Hysteresis.** The half-way points of melting and freezing are about 390 K apart: on cooling, the liquid
  stays liquid far below the temperature at which the crystal melted on heating. The gap depends on both
  rates; the equilibrium melting point of this cluster lies in between and was not computed.
- **Final structure.** Crystalline again, but not the starting icosahedron. hcp atoms, which in an fcc metal
  mark twin boundaries and stacking faults, still make up two thirds of the crystalline atoms, so the fcc
  regions are heavily twinned or faulted. In all 61 frames of the final hold the atom at the centre is
  "other", and the one icosahedral atom sits 7.9–8.2 Å from the centre of a cluster about 12.7 Å in radius
  (in 2 frames a second one appears, 9–10 Å out). In the starting icosahedron that atom is the central one.
- **Why Cu<sub>561</sub>.** A test with Cu<sub>147</sub> and the same schedule ended with 0.6 % crystalline
  atoms (21 % at the start): at that size and rate it froze into a disordered cluster
  (`data/cu147_cna_fractions.csv`). 92 of its 147 atoms sit on the surface, against 252 of 561 here.
- **Slower cooling did not crystallize.** The `slow-freeze` run (`data/cu561_slowfreeze_cna_fractions.csv`)
  is identical to the one shown, bit for bit, up to 100 ps; five picoseconds after the schedules split,
  some atoms already differ by more than an interatomic distance. Cooled at 1 K/ps from 1000 to 600 K, it
  stayed liquid: small crystalline patches came and went, the crystalline fraction stayed below 3 % down to
  600 K, and it ended at 4.2 % at 300 K, a disordered cluster. Nucleation is a random event, so one run per schedule cannot say how the cooling
  rate changes the outcome.

## Differences from standard practice

- **Cooling rate.** 2.75 × 10<sup>12</sup> K/s, typical of MD: roughly a million times faster than melt
  spinning (about 10<sup>6</sup> K/s). Only ultrafast quenching of nanoscale volumes comes close, up to about
  10<sup>14</sup> K/s (Zhong et al., *Nature* 512, 177, 2014). Fast cooling traps defects and whichever
  structure nucleates first, so the final structure is one possible outcome, not necessarily the
  lowest-energy one.
- **Thermostat coupling.** Friction 0.02 fs<sup>-1</sup> (velocity relaxation time 50 fs) holds the
  temperature close to the set point but also damps the atoms' motion, which slows diffusion and probably
  crystallization. The freezing temperatures above hold for this coupling only.
- **One trajectory.** A single run with one seed; melting and freezing temperatures from it have no error
  bars, and supercooling depends on the seed and the rate. The two schedules above show how much: the one
  that cooled slowly through the freezing range did not crystallize at all. A rate study needs many seeds
  per rate.
- **Potential.** EMT is a fast, approximate many-body potential; its melting point and surface energies differ
  from experiment and from density functional theory.
- **Surface atoms.** a-CNA labels atoms by their full neighbour shell, so surface atoms are "other" even in a
  perfect crystal: 252 of the 561 atoms (45 %) here.
- **Presentation.** The camera turn, the cut and the even spacing of the shown frames in time are for display
  only. The animation shows a subset of the saved frames, with a short fade at the loop.

## Rebuild

```bash
pip install -r requirements.txt
python animation/crystallization_md.py --shells 6           # about 3 h on one CPU core (i5-13400)
python animation/render_header.py --system cu561            # about 20 min; uses all cores
python animation/render_header.py --system cu147 --csv-only # fractions only, for the Cu147 test
python animation/crystallization_md.py --shells 6 --schedule slow-freeze   # about 4 h
python animation/render_header.py --system cu561_slowfreeze --csv-only
```

`render_header.py` uses Cascadia Mono (SIL Open Font License) from the Windows fonts folder; change `FONT` on
other systems.
