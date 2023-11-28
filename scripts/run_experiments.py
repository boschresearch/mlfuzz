#!/usr/bin/env python3
# Copyright (c) 2023 Robert Bosch GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This script runs fuzzing experiments inside Docker containers.

  - The following fuzzers are supported: AFL, AFL++, PreFuzz, original Neuzz based on AFL,
    Neuzz++ based on AFL++, Havoc MAB, MOPT, MOPT++, and Darwin.
  - The experiments are queued and distributed on cores.
  - The specification of the experiment is done in `experiment_config.yaml`
    (see default values in `experiment_config.yaml.default`).
  - Machine learning jobs can be run with GPU support (deactivated by default). If activated,
    only ML jobs will use GPUs.
"""
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

# Configure console logger
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("neuzzpp")

# Read experiment configuration
with open(Path(__file__).parent / "experiment_config.yaml", "r") as conf_file:
    config = yaml.load(conf_file, Loader=yaml.FullLoader)
binaries_folder = Path(config["binaries_folder"])
seeds_folder = Path(config["seeds_folder"])
results_folder = Path(config["results_folder"])

# Define supported fuzzers
Fuzzer = Enum("Fuzzer", "AFL AFLPP HAVOC NEUZZ NEUZZPP PREFUZZ DARWIN MOPT MOPTPP")
fuzzers = list(map(lambda fuzzer_name: Fuzzer[fuzzer_name.upper()], config["fuzzers"]))

# Define CPU and GPU range
free_cpus = set(range(config["n_cpus"]))
free_gpus = set(range(config["n_gpus"]))


@dataclass
class Job:
    """Class keeping track of jobs / experiments to launch."""

    target: Path
    fuzzer: str
    trial: int
    rng_seed: int
    pass_by_file: bool

    def name(self) -> str:
        if self.pass_by_file:
            return f"{self.target.name}_{self.fuzzer}_slow_trial-{self.trial}"

        return f"{self.target.name}_{self.fuzzer}_trial-{self.trial}"


@dataclass
class JobAssignment:
    """Class keeping track of assignment of jobs to CPUs/GPUs."""

    job: Job
    core_id: int
    gpu_id: Optional[int]

    def command(self) -> str:
        cmd = (
            f"docker run -d -u $(id -u):$(id -g) --name {self.job.name()} "
            f"-v {binaries_folder}:{binaries_folder} "
            f"-v {seeds_folder}:{seeds_folder} "
            f"-v {results_folder}:{results_folder} "
            f'--cpuset-cpus "{self.core_id}" '
        )
        if self.gpu_id is not None:
            cmd += f"--gpus '\"device={self.gpu_id}\"' "
        cmd += config["docker_image"] + " python "
        if self.job.fuzzer == Fuzzer.AFLPP.name:
            cmd += "/aflpp/run_aflpp.py "
        elif self.job.fuzzer == Fuzzer.NEUZZPP.name:
            cmd += "/neuzzpp/run_neuzzpp.py "
        elif self.job.fuzzer == Fuzzer.AFL.name:
            cmd += "/afl/run_afl.py "
        elif self.job.fuzzer == Fuzzer.HAVOC.name:
            cmd += "/havoc/run_havoc.py "
        elif self.job.fuzzer == Fuzzer.NEUZZ.name:
            cmd += "/neuzz/run_neuzz.py "
        elif self.job.fuzzer == Fuzzer.PREFUZZ.name:
            cmd += "/prefuzz/run_prefuzz.py "
        elif self.job.fuzzer == Fuzzer.DARWIN.name:
            cmd += "/darwin/run_darwin.py "
        elif self.job.fuzzer == Fuzzer.MOPT.name:
            cmd += "/mopt/run_mopt.py "
        elif self.job.fuzzer == Fuzzer.MOPTPP.name:
            cmd += "/moptpp/run_moptpp.py "
        else:
            raise ValueError(f"Unknown fuzzer: {self.job.fuzzer}.")
        cmd += (
            f"{seeds_folder / self.job.target.stem} "
            f"{results_folder / self.job.target.stem / self.job.fuzzer}/trial-{self.job.trial} "
            f"{self.job.target} -d {config['duration']} -s {self.job.rng_seed} "
        )
        if self.job.pass_by_file:
            cmd += "--pass_by_file"

        return cmd


def get_targets(
    path: Path, targets: List[str], fuzzers: List[Fuzzer]
) -> Tuple[Optional[List[Path]], Optional[List[Path]]]:
    """
    Read the list of targets for fuzzing from a given folder, then split them according to
    their compilation options (detected via target extension).

    Args:
        path: Folder containing the compiled binaries to fuzz.
        targets: List of target names without extension.
        fuzzers: List of fuzzers specified for the current experiment.

    Returns:
        Two lists of targets, one with targets built for AFL, the other for AFL++.
        If any of the two types of targets are not required for the experiment, the corresponding
        list will be `None`.
    """
    targets_afl, targets_aflpp = None, None
    if (
        Fuzzer.AFL in fuzzers
        or Fuzzer.NEUZZ in fuzzers
        or Fuzzer.PREFUZZ in fuzzers
        or Fuzzer.HAVOC in fuzzers
        or Fuzzer.DARWIN in fuzzers
        or Fuzzer.MOPT in fuzzers
    ):
        targets_afl = [path / (target + ".afl") for target in targets]

    if Fuzzer.AFLPP in fuzzers or Fuzzer.NEUZZPP in fuzzers or Fuzzer.MOPTPP in fuzzers:
        targets_aflpp = [path / (target + ".aflpp") for target in targets]

    return targets_afl, targets_aflpp


# Get targets for experiment
targets_afl, targets_aflpp = get_targets(binaries_folder, config["targets"], fuzzers)

# Create empty seeds for targets that do not have any
for target_name in config["targets"]:
    os.makedirs(seeds_folder / target_name, exist_ok=True)
    if next((seeds_folder / target_name).iterdir(), None) is None:
        with open(seeds_folder / target_name / "default_seed", "w") as seed_handle:
            seed_handle.write("hi")  # Default seed from Fuzzbench

# Create jobs
jobs = []
for fuzzer in fuzzers:
    if fuzzer in (Fuzzer.AFLPP, Fuzzer.NEUZZPP, Fuzzer.MOPTPP):
        current_targets = targets_aflpp
    else:
        current_targets = targets_afl

    if current_targets is not None:
        for target in current_targets:
            for trial, rng_seed in enumerate(config["rng_seeds"][: config["n_trials"]]):
                jobs.append(
                    Job(
                        target=target,
                        fuzzer=fuzzer.name,
                        trial=trial,
                        rng_seed=rng_seed,
                        pass_by_file=config["pass_by_file"],
                    )
                )
logger.info(f"{len(jobs)} jobs to create.")

# Launch jobs
running: List[JobAssignment] = []
while jobs or running:
    # Check finished jobs
    finished: List[Job] = []
    for current in running:
        code = subprocess.call(
            f"docker ps -a | grep {current.job.name()} | grep Exited",
            shell=True,
        )
        if code == 0:
            logger.info(f"{current.job.name()} finished.")
            running.remove(current)
            finished.append(current.job)
            free_cpus.add(current.core_id)
            if current.gpu_id is not None:
                free_gpus.add(current.gpu_id)

    # Clean-up finished jobs
    for job in finished:
        # Save Docker log
        job_name = job.name()
        logs = subprocess.check_output(["docker", "logs", job_name])
        job_folder = results_folder / job.target.stem / job.fuzzer / ("trial-" + str(job.trial))
        out_folder = job_folder / "default" if (job_folder / "default").is_dir() else job_folder
        with open(out_folder / "docker.log", "w") as log_file:
            log_file.write(logs.decode("utf-8"))

        # Check exit code
        exitcode = subprocess.check_output(
            ["docker", "inspect", job_name, "--format='{{.State.ExitCode}}'"], encoding="utf-8"
        ).strip("'\n")
        if int(exitcode) == 0:
            rm_ok = subprocess.call(["docker", "rm", job_name])
            if rm_ok != 0:
                logger.warning(f"{job_name}: Docker rm failed with exit code {rm_ok}.")
        else:
            logger.warning(f"{job_name}: container exited with code {exitcode}.")

    # No more jobs or no more CPU/GPU, wait for someone to finish
    if not jobs or not free_cpus or (config["use_gpu"] and not free_gpus):
        time.sleep(10)
        continue

    # Launch one new job
    job = jobs.pop(0)
    job_name = job.name()
    core_id = free_cpus.pop()
    if config["use_gpu"] and job.fuzzer in [
        Fuzzer.NEUZZ.name,
        Fuzzer.NEUZZPP.name,
        Fuzzer.PREFUZZ.name,
    ]:
        gpu_id = free_gpus.pop()
        new_job = JobAssignment(job, core_id, gpu_id)
    else:
        new_job = JobAssignment(job, core_id, None)
    job_folder = results_folder / job.target.stem / job.fuzzer / ("trial-" + str(job.trial))
    try:
        os.makedirs(job_folder, exist_ok=True)
    except OSError:
        logger.warning(f"Failed to create output folder {job_folder}. Skipping job.")
        continue

    cmd = new_job.command()
    logger.info(f"Running experiment {job_name} on core {core_id}.")
    launch_code = subprocess.call(cmd, shell=True)
    if launch_code != 0:
        logger.warning(f"{job_name}: {cmd} returned {launch_code}.")
    else:
        running.append(new_job)

logger.info("All jobs finished. Exiting.")
