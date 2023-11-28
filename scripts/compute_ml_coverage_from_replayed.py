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
Script for computing the coverage obtained by machine learning seeds of fuzzers
NEUZZ, NEUZZPP and PREFUZZ.

The coverage is extracted from existing `replayed_plot_data` files of each run by matching
seed names with obtained coverage based on timestamps.
"""
import argparse
import logging
import pathlib
import sys
from typing import Sequence

import numpy as np
import pandas as pd

from neuzzpp.utils import get_timestamp_millis_from_filename

# Configure logger - console
logger = logging.getLogger("neuzzpp")
logger.setLevel(logging.INFO)
console_logger = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_logger.setFormatter(log_formatter)
logger.addHandler(console_logger)


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("results_folder", help="output folder from an experiment", type=str)
    args = parser.parse_args(argv[1:])

    res = {}
    for target in pathlib.Path(args.results_folder).glob("*"):
        for fuzzer in target.glob("*"):
            # Choose seed name pattern based on fuzzer name
            if fuzzer.name == "NEUZZPP":
                seed_pattern = "ml-mutator"
            elif fuzzer.name in ["NEUZZ", "PREFUZZ"]:
                seed_pattern = "id_"
            else:
                continue

            ml_cov = []
            for plot_data_file in fuzzer.glob("**/replayed_plot_data"):
                trial_folder = plot_data_file.parent

                # Read replayed coverage
                cov_data = pd.read_csv(plot_data_file, sep=", ", engine="python")

                # Get seeds list ordered by timestamp in filename
                seeds_path = trial_folder / "queue"
                seed_list = [seed for seed in seeds_path.glob("id*")]
                seed_list = sorted(
                    seed_list, key=lambda f: get_timestamp_millis_from_filename(f.name)
                )

                # Merge seed names and their coverage, then filter and sum for ML coverage
                cov_data["seed"] = seed_list
                cov_data["seed"] = cov_data["seed"].apply(lambda x: str(x))
                cov_data["cov_diff"] = cov_data.edges_found.diff()
                cov_data = cov_data[cov_data["seed"].str.contains(seed_pattern)]
                ml_cov.append(cov_data.cov_diff.sum())

                res[(target.name, fuzzer.name)] = (int(np.mean(ml_cov)), np.std(ml_cov))

    cov_dict = {
        "index": list(res.keys()),
        "index_names": ["target", "fuzzer"],
        "columns": [
            "Avg. edge cov.",
            "Std. dev.",
        ],
        "column_names": ["metrics"],
        "data": list(res.values()),
    }

    cov_pd = pd.DataFrame.from_dict(cov_dict, orient="tight")
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(cov_pd.round(2))


if __name__ == "__main__":
    main()
