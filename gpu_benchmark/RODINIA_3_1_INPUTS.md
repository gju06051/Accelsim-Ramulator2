# Rodinia 3.1 Input Audit

Base directory:

```text
/home/gju06051/Sectored-Access-DRAM/gpu_benchmark/gpu-app-collection/src/cuda/rodinia/3.1
```

Rodinia 2.0-ft has been removed from this local tree. The remaining built
Rodinia binaries are the 21 `*-rodinia-3.1` executables under
`gpu-app-collection/bin/12.3/release`.

The original checkout did not contain `src/cuda/rodinia/3.1/data`, and the
shared `gpu-app-collection/data_dirs` directory is still empty until the large
official dataset bundle is fetched.

Local small inputs that can be generated from bundled generators are handled by:

```bash
./generate_rodinia_3_1_inputs.sh
```

This has been run once locally and produced:

- `data/nn/cane4_0.db` through `data/nn/cane4_3.db`
- `data/lud/64.dat`, `data/lud/l-64.dat`, and `data/lud/u-64.dat`

## Can Run Without External Input Data

These workloads either generate data internally from command-line arguments or
use synthetic/random inputs:

- `backprop-rodinia-3.1 65536`
- `gaussian-rodinia-3.1 -s 64 -q`
- `lavaMD-rodinia-3.1 -boxes1d 10`
- `lud-rodinia-3.1 -s 64`
- `myocyte-rodinia-3.1 100 1 0`
- `nw-rodinia-3.1 64 10`
- `particlefilter_naive-rodinia-3.1 -x 128 -y 128 -z 10 -np 1000`
- `particlefilter_float-rodinia-3.1 -x 128 -y 128 -z 10 -np 1000`
- `pathfinder-rodinia-3.1 100 100 20`
- `srad_v2-rodinia-3.1 128 128 0 31 0 31 0.5 2`
- `streamcluster-rodinia-3.1 10 20 256 65536 65536 1000 none output.txt 1`

## Local Generators Found

- `cuda/nn/gen_dataset.sh` calls `cuda/nn/hurricane_gen`.
  `hurricane_gen` writes `data/cane<N>_<i>.db` relative to its current working
  directory. The existing `cuda/nn/filelist_4` expects
  `../../data/nn/cane4_*.db`, so the wrapper links `cuda/nn/data` to
  `3.1/data/nn/` before running the generator.
- `cuda/lud/tools/gen_input.c` can generate matrix files such as `64.dat`,
  `l-64.dat`, and `u-64.dat`. For normal smoke runs this is optional because
  `lud-rodinia-3.1 -s <N>` generates internally.
- `cuda/mummergpu/src/genreads.py` can generate query reads from a reference
  FASTA file, but it does not provide the reference itself. It also uses Python
  2 syntax.

## Mentions Generator But Missing Here

- `cuda/gaussian/README.txt` mentions `matrixGenerator.py` in a data folder, but
  that data folder/script is not present in this checkout. The `-s <N>` mode is
  available and avoids external input.
- `cuda/srad/srad_v1/README` says the input image is expanded from `image.pgm`,
  but `image.pgm` is not present. SRAD v2 is the data-free version.
- `cuda/huffman/testdatagen.h` exists, but the run script expects
  `../../data/huffman/test1024_H2.206587175259.in`; no standalone generator
  script was found.

## Needs External Data

These stock run scripts point to `../../data/...` files that are not currently
present:

- `b+tree`: `data/b+tree/mil.txt`, `data/b+tree/command.txt`
- `bfs`: `data/bfs/graph1MW_6.txt`
- `cfd`: `data/cfd/*.domn.*`
- `dwt2d`: BMP images such as `192.bmp` or `rgb.bmp`
- `heartwall`: `data/heartwall/test.avi`
- `hotspot`, `hotspot3D`: temp/power input files
- `huffman`: compressed input `.in` file
- `kmeans`: `data/kmeans/kdd_cup`
- `leukocyte`: `data/leukocyte/testfile.avi`
- `mummergpu`: reference/query FASTA files
- `nn`: hurricane DB files; the local wrapper now generates the small
  `cane4_*.db` set
- `srad_v1`: `data/srad/image.pgm`
