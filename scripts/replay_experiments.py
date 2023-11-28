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
"""
Script for replaying the corpora of multiple fuzzing trials to extract coverage information.
For each trial, the coverage data will be written in its respective folder in `replayed_plot_data`.

The target binaries are searched in `/shared/binaries`.
The following structure is assumed about the experiment folder:

  <exp_name>/<target>/<fuzzer>/trial-<index>/<fuzzer_output>

or

  <exp_name>/<target>/<fuzzer>/trial-<index>/default/<fuzzer_output>

These are compatible with output from AFL, AFL++ and other fuzzers based on them.
"""
import argparse
import logging
import pathlib
import subprocess
import sys
from typing import Sequence

# Configure console logger
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("neuzzpp")


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("results_folder", help="output folder from an experiment", type=str)
    args = parser.parse_args(argv[1:])

    binaries_folder = pathlib.Path("/shared/binaries")
    scripts_folder = pathlib.Path(__file__).parent.resolve()

    for target in pathlib.Path(args.results_folder).glob("*"):
        target_path = binaries_folder / (target.name + ".afl")
        for trial in target.glob("**/plot_data"):
            trial_results_folder = trial.parent
            out_file = trial_results_folder / "replayed_plot_data"

            # Run corpus replay for one trial
            if not out_file.exists():
                print(out_file)
                try:
                    subprocess.run(
                        [
                            scripts_folder / "replay_corpus.py",
                            trial_results_folder / "queue",
                            out_file,
                            target_path,
                        ]
                    )
                except subprocess.CalledProcessError as err:
                    logger.warning(f"{err.output}. Skipping trial.")


if __name__ == "__main__":
    main()
