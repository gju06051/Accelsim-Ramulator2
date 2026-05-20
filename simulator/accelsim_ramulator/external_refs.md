# External Simulator References

This integration layer is intended to run next to the AccelSim/GPGPU-Sim and
Ramulator2 source trees. The all-in-one checkout already provides those trees
under `simulator/`.

## Expected Layout

```text
../gpgpu-sim_distribution
../ramulator2
```

## Current Known References

The bundled simulator trees currently correspond to these working branches:

```text
gpgpu-sim_distribution: branch dev
ramulator2: branch hbm4-baseline
```

Update this file whenever the bridge or overlay starts relying on a specific
simulator commit or API shape.
