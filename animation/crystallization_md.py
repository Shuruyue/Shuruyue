"""Molecular dynamics of a Cu nanocluster (Mackay icosahedron, 147 or 561 atoms): melt it, then cool it until it crystallizes again.

Potential: effective medium theory (EMT, Jacobsen, Stoltze & Norskov 1996) as shipped with ASE.
Thermostat: Langevin. The temperature follows a piecewise-linear schedule (see SCHEDULES; --schedule picks one).

Output: animation/data/cu<N>_md.npz with positions (frames x atoms x 3, Angstrom), time (ps),
target temperature (K) and instantaneous kinetic temperature (K) for every saved frame.

Run:  python animation/crystallization_md.py --shells 6 (Cu561, full run, ~100k steps)
      python animation/crystallization_md.py --smoke    (a few hundred steps, timing only)
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from ase import units
from ase.calculators.emt import EMT
from ase.constraints import FixCom
from ase.cluster import Icosahedron
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import Stationary, ZeroRotation, thermalize_momenta

# (duration in ps, temperature at the end of the segment in K); the run starts at T_START.
T_START = 300.0
SCHEDULES = {
    # 2.75 K/ps all the way down
    "fast": [
        (20.0, 300.0),    # equilibrate the Mackay icosahedron
        (60.0, 1400.0),   # heat well above the cluster's melting range
        (20.0, 1400.0),   # hold: fully liquid
        (400.0, 300.0),   # cool at 2.75 K/ps
        (30.0, 300.0),    # hold
    ],
    # same heating; 4 K/ps to 1000 K, then 1 K/ps through the freezing range, then 3 K/ps to 300 K
    "slow-freeze": [
        (20.0, 300.0),
        (60.0, 1400.0),
        (20.0, 1400.0),
        (100.0, 1000.0),
        (400.0, 600.0),
        (100.0, 300.0),
        (30.0, 300.0),
    ],
}
DT_FS = 5.0
SAVE_EVERY = 100          # steps between saved frames (0.5 ps)
FRICTION_PER_FS = 0.02
SEED = 7

DATA = Path(__file__).resolve().parent / "data"


def target_temperature(t_ps: float, schedule: list) -> float:
    t0, temp0 = 0.0, T_START
    for duration, temp1 in schedule:
        if t_ps <= t0 + duration:
            return temp0 + (temp1 - temp0) * (t_ps - t0) / duration
        t0, temp0 = t0 + duration, temp1
    return temp0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run 300 steps and report timing")
    parser.add_argument("--shells", type=int, default=4, help="4 -> Cu147, 5 -> Cu309, 6 -> Cu561")
    parser.add_argument("--schedule", choices=sorted(SCHEDULES), default="fast")
    args = parser.parse_args()
    schedule = SCHEDULES[args.schedule]

    atoms = Icosahedron("Cu", noshells=args.shells)
    suffix = "" if args.schedule == "fast" else "_" + args.schedule.replace("-", "")
    out = DATA / f"cu{len(atoms)}{suffix}_md.npz"
    atoms.center(vacuum=10.0)
    atoms.calc = EMT()
    atoms.set_constraint(FixCom())  # keep the cluster in place; ASE's recommended form

    rng = np.random.default_rng(SEED)
    thermalize_momenta(atoms, temperature_K=T_START, rng=rng)
    Stationary(atoms)
    ZeroRotation(atoms)

    dyn = Langevin(atoms, DT_FS * units.fs, temperature_K=T_START,
                   friction=FRICTION_PER_FS / units.fs, rng=rng, fixcm=False)

    total_ps = sum(d for d, _ in schedule)
    n_steps = 300 if args.smoke else int(round(total_ps * 1000.0 / DT_FS))
    frames, times, targets, kinetic = [], [], [], []
    t_wall = time.perf_counter()
    for step in range(n_steps + 1):
        t_ps = step * DT_FS / 1000.0
        if step % SAVE_EVERY == 0:
            frames.append(atoms.get_positions().astype(np.float32))
            times.append(t_ps)
            targets.append(target_temperature(t_ps, schedule))
            kinetic.append(atoms.get_temperature())
            if step % (SAVE_EVERY * 100) == 0:
                elapsed = time.perf_counter() - t_wall
                print(f"step {step:>7d}/{n_steps}  t={t_ps:7.1f} ps  "
                      f"T_target={targets[-1]:7.1f} K  T_kin={kinetic[-1]:7.1f} K  "
                      f"wall={elapsed / 60:6.1f} min", flush=True)
        if step == n_steps:
            break
        dyn.set_temperature(temperature_K=target_temperature(t_ps, schedule))
        dyn.run(1)

    per_step = (time.perf_counter() - t_wall) / max(n_steps, 1)
    print(f"{per_step * 1e3:.1f} ms/step; full run would take "
          f"{per_step * total_ps * 1000.0 / DT_FS / 60:.0f} min")
    if args.smoke:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, positions=np.array(frames), time_ps=np.array(times),
                        target_K=np.array(targets), kinetic_K=np.array(kinetic),
                        dt_fs=DT_FS, save_every=SAVE_EVERY, seed=SEED,
                        schedule=np.array(schedule), schedule_name=args.schedule)
    print(f"saved {len(frames)} frames to {out}")


if __name__ == "__main__":
    main()
