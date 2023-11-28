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
This script extracts coverage data from an experiment folder.
Mean coverage, standard deviation and coverage plots are produced for the folder.

The following structure is assumed about the experiment folder:

  <exp_name>/<target>/<fuzzer>/trial-<index>/<fuzzer_output>

or

  <exp_name>/<target>/<fuzzer>/trial-<index>/default/<fuzzer_output>

These are compatible with output from AFL, AFL++ and other fuzzers based on them.
"""
import argparse
import logging
import pathlib
import sys
from typing import Sequence

import matplotlib.pyplot as plt
import pandas as pd

from neuzzpp.utils import compute_coverage_experiment, create_plot_afl_coverage

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

    # Compute and print average coverage for experiment
    cov = compute_coverage_experiment(args.results_folder)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(cov.round(2))  # or as Latex with cov.style.to_latex()

    # Generate coverage plots and store them at the root of the experiments folder
    curr_folder = pathlib.Path.cwd()
    for target in pathlib.Path(args.results_folder).glob("*"):
        plt.clf()
        plot = create_plot_afl_coverage(target, plot_file="replayed_plot_data")
        plot.set_title("")
        plt.savefig(curr_folder / (str(target) + ".pdf"), bbox_inches="tight")


if __name__ == "__main__":
    main()
