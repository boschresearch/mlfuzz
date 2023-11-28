# MLFuzz - fuzzing with machine learning

MLFuzz is a framework that allows benchmarking fuzzers.
Its focus is around fuzzing with machine learning or other optimization techniques.
This is the companion code for the benchmarking study reported in the paper ["Revisiting Neural Program Smoothing for Fuzzing"](https://arxiv.org/abs/2309.16618) presented at ESEC/FSE'23.
The code allows the users to reproduce and extend the results reported in the paper.
See also the [Neuzz++ implementation](https://github.com/boschresearch/neuzzplusplus) introduced in the same paper.

## Setup

MLFuzz has been tested on Ubuntu 20.04 LTS.
This project uses `docker` to containerize dependency installation, build targets and run experiments.
Please see the official [installation page](https://docs.docker.com/engine/install/).

### Build benchmark targets

We first build the 23 programs that will be used as targets for experiments:

    cd MLFuzz/benchmarks
    make

### Build experiment environment

Build Docker image for running experiments:

    docker build . -t mlfuzz

This will make the `mlfuzz` image available for single or batch experiments.

### Installing Python dependencies

All scripts for facilitating batch experiments and results post-processing are written in Python.
This project uses `python>=3.8` and [`poetry`](https://python-poetry.org/) for managing the Python environment.
Install `poetry` system-wide or in an empty virtual environment (e.g., created via `virtualenv` or `conda`).
Then run

    poetry install --without dev

to install the project dependencies.
Note that Neuzz++ and MLFuzz have the same Python dependencies; you only need to create one virtual environment for both of them.
Use

    poetry shell

to activate the environment.

### Configuring CPUs for performance

Fuzzing is resource-intensive, especially in terms of CPU usage.
All fuzzers in the AFL family require changes to the CPU configuration of the system they run on.
To make these, run the following commands as root on your system:

    echo core >/proc/sys/kernel/core_pattern
    cd /sys/devices/system/cpu
    echo performance | tee cpu*/cpufreq/scaling_governor

You can later go back to the original state by replacing `performance` with `ondemand` or `powersave`. If you don't want to change the settings, set `AFL_SKIP_CPUFREQ` on all experiment runs to make `afl-fuzz` skip this check - but expect some performance drop.

## Usage

Once all the setup steps have been performed, the environment is ready to run single or batch experiments.

### Single experiment

To run a single fuzzing trial, e.g., fuzzing `json`, using the `mlfuzz` Docker image created above, run:

    docker run --rm -it -v $(pwd)/benchmarks/binaries/:/targets/ -e AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 \
      -e AFL_FORKSRV_INIT_TMOUT=1000 -e AFL_DISABLE_TRIM=1 -e AFL_CUSTOM_MUTATOR_LIBRARY=/neuzzpp/aflpp-plugins/libml-mutator.so \
      mlfuzz /aflpp/afl-fuzz -i /targets/seeds/libjpeg-turbo-07-2017/ -o /output -m none -- /targets/libjpeg-turbo-07-2017

The `--rm` removes the container after completion.
With `-d` you can run the container in background.
`--name` can assign a name to the container for later access.
Not every target in Fuzzer Test Suite has seeds.
If the seeds folder is missing for the target of your choice, create an empty folder and place at least one non-empty test case in that folder.

### Batch experiments

MLFuzz uses a configuration file to specify an experiment plan.
The repo includes configuration defaults in `scripts/experiment_config.yaml.default`.
First make a copy of this file without the `.default` suffix:

    cp scripts/experiment_config.yaml.default scripts/experiment_config.yaml

Then edit the newly created `scripts/experiment_config.yaml` for your own experiment plan.
* Configure hardware access by choosing the number of CPUs and (optionally) GPUs in the fields `n_cpus`, `n_gpus` and `use_gpus`. If `use_gpus` is `False`, `n_gpus` will be ignored, and all experiments will run on CPU.
* Configure local paths:
    * `binaries_folder` should indicate the folder of the target programs, i.e., from the `Build benchmark targets` step above
    * `seeds_folder` points to the folder that contains seed test cases for each target, also from the `Build benchmark targets` step
    * `results_folder` will store the output of all experiments.
* Configure fuzzing options:
   * `duration` specifies how long each fuzzer should run *in seconds*.
   * `n_trials` is the number of repetitions of each experiment.
* The configuration specifies all the available fuzzers and target programs. Edit these lists to your needs.

The next step requires the `mlfuzz` Docker image built above and the Python environment.
Use the command

    ./scripts/run_experiments.py

to run batch experiments.
This script starts and manages all experiment runs from the configuration file.
For long experiments, consider running it in the background with `&` or running it in a [`screen`](https://linux.die.net/man/1/screen) session.

## Reproducing experiments

This section is dedicated to reproducing the experiments from the ESEC/FSE '23 paper mentioned below.
Note that over 11 CPU years and 5.5 GPU years were used to compute the results presented in the paper.
As such, please only try to reproduce them at scale if you have extensive computing resources.

We mainly follow the structure of the Experiments section in the paper when providing instructions to reproduce it.
Note that the subsections are not necessarily in the order presented in the paper, but that which makes them easier to reproduce.
For easier identification, the section numbering and names match those in the paper.
We consider the starting point to be a working installation of MLFuzz with a default configuration file.
If you are using different paths or hardware, please adapt those values.

### 5.3 Comparing code coverage - main experiment

To run the main experiment (Tab. 3), set `n_trials: 30`, `duration: 86400` (24 hours) and `use_gpus: True` in the configuration file.
All 23 targets programs are used with 6 fuzzers: `afl`, `aflpp`, `havoc`, `neuzz`, `neuzzpp` and `prefuzz`.
Then run the main experiments script:

    ./scripts/run_experiments.py

Run the following script with the output folder as argument to aggregate the results to the values in Tab. 3 and to produce the coverage plots in Fig. 4:

    ./scripts/generate_coverage_report_experiments.py /shared/results/baselines

The script prints the averaged coverage values for all targets and fuzzers.
The coverage plots are saved in the output folder of the experiments.

### 5.4 Code coverage from machine learning

This experiment uses the results from the previous experiment.
To produce the results from Tab. 4, run:

    ./scripts/compute_ml_coverage_from_replayed.py /shared/results/baselines

### 5.2 Performance of machine learning models

This experiment uses the results from 5.3.
Each experiment folder produced by MLFuzz contains the Docker logs for that run in the output folder under `docker.log`.
The last lines in each log contain the machine learning evaluation metrics from Tab. 2.
Adapting the script `./scripts/extract_ml_prc.sh` to each of the metric names can be used to automatically extract and average the values from the logs.

The coverage plots in Fig. 3 are obtained using the [Jupyter notebook](../NEUZZplusplus/notebooks/analysis_ml_oracle_coverage.ipynb) in the Neuzz++ artifact for program `libpng-1.2.56`.
The notebook can produce similar plots for all targets by changing the name of the program analyzed.

### 5.5 Quality of machine learning test cases

This experiment uses the results from 5.3.
To reproduce the metrics from Tab. 5, run:

    ./scripts/compute_ml_seeds_stats.py /shared/results/baselines

Similarly, to compute the results from Tab. 6, run:

    ./scripts/compare_edge_ids.py /shared/results/baselines

### 5.6 NPS-based fuzzing without GPUs

This experiment compares fuzzing performance for the same experiments run on CPUs only, or CPUs and GPUs jointly.
The metrics in Tab. 7 use the results from experiment 5.3 for the GPU columns (only the first 10 runs).

To obtain the CPU-only columns, edit the experiment configuration file as follows:
* Keep fuzzers `neuzz`, `neuzzpp` and `prefuzz`.
* Keep targets `harfbuzz-1.3.2`, `libjpeg-turbo-07-2017`, `sqlite-2016-11-14` and `woff2-2016-05-06`.
* Set `n_trials: 10`, `duration: 86400`, `use_gpus: False`.
* Change `results_folder` to a path that does not overlap with prior experiments.

Then run the experiments as before:

    ./scripts/run_experiments.py

Finally, compute the coverage metrics by running:

    ./scripts/generate_coverage_report_experiments.py <results_folder>

where `<results_folder>` is the output path specified in the experiment configuration.

### 5.7 Impact of test case transmission method

This experiment compares fuzzing performance for the same experiments run with test case transmission via files or via shared memory.

To obtain the file-based transmission performance, edit the experiment configuration file as follows:
* Keep fuzzers `afl`, `aflpp`, `havoc`, `neuzz`, `neuzzpp` and `prefuzz`.
* Keep targets `harfbuzz-1.3.2`, `libjpeg-turbo-07-2017`, `sqlite-2016-11-14` and `woff2-2016-05-06`.
* Set `n_trials: 10`, `duration: 86400`, `use_gpus: True` and `pass_by_file: True`.
* Change `results_folder` to a path that does not overlap with prior experiments.

Then run the experiments as before:

    ./scripts/run_experiments.py

Compute the coverage metrics by running:

    ./scripts/generate_coverage_report_experiments.py <results_folder>

The results in Tab. 8 are computed from the current values relatively to the corresponding results from experiment 5.3.

### 5.8 Bugs found

This section analyzes the crashes from the experiments in section 5.3.
The results in Tab. 9 are obtained by running:

    ./scripts/analyze_crashes.py /shared/results/baselines /shared/results/binaries

## Project structure

    MLFuzz/
    ├── benchmarks/             # Folder containing Dockerfile and scripts for building fuzzing targets
    ├── fuzzers/                # Folder containing scripts for running each fuzzer in a Docker container
    ├── mlfuzz/                 # Python package with reusable utility functions
    ├── scripts/                # Scripts for running experiments and postprocessing results
    ├── CONTRIBUTING.md         # Guidelines for contributing extension to MLFuzz
    ├── Dockerfile              # Dockerfile for the image running experiments
    ├── LICENSE                 # License file
    ├── poetry.lock             # Project requirements in Poetry format
    ├── pyproject.toml          # Standard Python package description for pip
    └── README.md               # The present README file

## Contributing

The integration of new fuzzers or targets is welcome.
See [CONTRIBUTING](CONTRIBUTING.md) guidelines before opening a pull request.

## Citation

If you use MLFuzz in scientific work, consider citing our paper presented at ESEC/FSE '23:

    Maria-Irina Nicolae, Max Eisele, and Andreas Zeller. “Revisiting Neural Program Smoothing for Fuzzing”. In Proceedings of the 31st ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering. ACM, Dec. 2023.

<details>
<summary>BibTeX</summary>

  ```bibtex
  @inproceedings {MLFuzz23,
  author = {Maria-Irina Nicolae, Max Eisele, and Andreas Zellere},
  title = {Revisiting Neural Program Smoothing for Fuzzing},
  booktitle = {Proceedings of the 31st ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering (ESEC/FSE)},
  year = {2023},
  publisher = {{ACM}},
  doi = {10.1145/3468264.3473932},
  month = dec,
  }
  ```

</details>

## License

Copyright (c) 2023 Robert Bosch GmbH and its subsidiaries.
MLFuzz is distributed under the Apache-2.0 license.
See the [LICENSE](LICENSE) for details.
