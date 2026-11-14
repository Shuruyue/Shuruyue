"""Check the MD time step: constant-energy (NVE) runs of the 1400 K liquid at several time steps.

Start: the cluster at the end of the 1400 K hold (t = 100 ps) of a saved trajectory, with fresh
Maxwell-Boltzmann velocities at 1400 K (the trajectory stores no velocities). Every time step starts
from the same positions and velocities and runs 2 ps of velocity Verlet with EMT. Drift is the slope of
a straight-line fit to the total energy; RMS is the scatter of the total energy around that line.

Output: animation/data/timestep_check.csv (one row per time step).

Run:  python animation/timestep_check.py [--system cu561] [--dt 5 2]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from ase import Atoms, units
from ase.calculators.emt import EMT
from ase.md.velocitydistribution import Stationary, ZeroRotation, thermalize_momenta
from ase.md.verlet import VelocityVerlet

DATA = Path(__file__).resolve().parent / "data"
START_PS = 100.0       # end of the 1400 K hold in both schedules
TEMPERATURE_K = 1400.0
RUN_PS = 2.0
SEED = 7


def nve(positions: np.ndarray, dt_fs: float) -> dict:
    atoms = Atoms(f"Cu{len(positions)}", positions=positions)
    atoms.center(vacuum=10.0)
    atoms.calc = EMT()
    thermalize_momenta(atoms, temperature_K=TEMPERATURE_K, rng=np.random.default_rng(SEED))
    Stationary(atoms)
    ZeroRotation(atoms)
    n = len(atoms)
    times, energies, temps = [], [], []

    def record() -> None:
        times.append(dyn.nsteps * dt_fs / 1000.0)
        energies.append((atoms.get_potential_energy() + atoms.get_kinetic_energy()) / n * 1000.0)  # meV/atom
        temps.append(atoms.get_temperature())

    dyn = VelocityVerlet(atoms, timestep=dt_fs * units.fs)
    dyn.attach(record, interval=1)
    dyn.run(int(round(RUN_PS * 1000.0 / dt_fs)))
    t, e = np.array(times), np.array(energies)
    slope, intercept = np.polyfit(t, e, 1)
    return {"dt_fs": dt_fs, "drift_meV_per_atom_ps": slope,
            "rms_meV_per_atom": float(np.sqrt(np.mean((e - (slope * t + intercept)) ** 2))),
            "mean_T_K": float(np.mean(temps)), "steps": len(t) - 1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", default="cu561", help="trajectory to start from: data/<system>_md.npz")
    parser.add_argument("--dt", type=float, nargs="+", default=[5.0, 2.0], help="time steps in fs")
    args = parser.parse_args()

    md = np.load(DATA / f"{args.system}_md.npz")
    k = int(np.argmin(np.abs(md["time_ps"] - START_PS)))
    print(f"{args.system}: start frame at t = {md['time_ps'][k]:.1f} ps, set point {md['target_K'][k]:.0f} K")
    rows = []
    for dt_fs in args.dt:
        row = nve(md["positions"][k].astype(np.float64), dt_fs)
        rows.append(row)
        print(f"dt = {dt_fs:g} fs: drift {row['drift_meV_per_atom_ps']:+.4f} meV/atom/ps, "
              f"RMS {row['rms_meV_per_atom']:.4f} meV/atom, mean T {row['mean_T_K']:.0f} K, "
              f"{row['steps']} steps", flush=True)
    keys = list(rows[0])
    np.savetxt(DATA / "timestep_check.csv", [[r[c] for c in keys] for r in rows], delimiter=",",
               fmt="%.4f", header=",".join(keys), comments="")


if __name__ == "__main__":
    main()
