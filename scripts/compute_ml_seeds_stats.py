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
This script computes some statistics about ML-derived test cases in the Neuzz++ corpus.

The following structure is assumed about the experiment folder:
     <exp_name>/<target>/NEUZZPP/trial-<index>/default/<fuzzer_output>


The following information is computed:
  * The absolute no. of ML seeds
  * The percentage of ML seeds w.r.t. the size of the corpus
  * The no. of ML seeds that increase coverage
  * The percentage of test cases in the corpus that are derived from ML test cases.
"""
import argparse
import logging
import pathlib
import re
import sys
from typing import List, Sequence, Set

import numpy as np
import pandas as pd

# Configure logger - console
logger = logging.getLogger("neuzzpp")
logger.setLevel(logging.INFO)
console_logger = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_logger.setFormatter(log_formatter)
logger.addHandler(console_logger)

seed_id_extractor = re.compile(r"id:(\d{6})*")
seed_src_extractor = re.compile(r"id:\d{6},src:(\d{6})(?:\+(\d{6})?)*")


def get_seed_id(seed_name: str) -> int:
    matches = seed_id_extractor.match(seed_name)
    seed_id = int(matches.group(1))
    return seed_id


def find_descendants(path: pathlib.Path, seed_id: int) -> List[pathlib.Path]:
    new_seeds = []
    for seed in path.glob("id*"):
        matches = seed_src_extractor.findall(str(seed))
        derived_ids = [int(t) for m in matches for t in m if t != ""]
        if seed_id in derived_ids:
            new_seeds.append(seed)
    return new_seeds


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("results_folder", help="output folder from an experiment", type=str)
    args = parser.parse_args(argv[1:])

    stats = {}
    for target in pathlib.Path(args.results_folder).glob("*"):
        for fuzzer in target.glob("NEUZZPP"):
            n_ml_seeds_trials = []
            perc_ml_seeds_trials = []
            n_ml_seeds_cov_trials = []
            n_ml_derived_trials = []
            for queue_folder in fuzzer.glob("**/queue"):
                seed_list = [seed for seed in queue_folder.glob("id:*")]
                ml_seed_list = [seed for seed in queue_folder.glob("id:*ml-mutator*")]

                n_seeds = len(seed_list)
                n_ml_seeds = len(ml_seed_list)
                n_ml_seeds_cov = len([seed for seed in queue_folder.glob("id:*ml-mutator*+cov")])
                assert n_seeds >= n_ml_seeds
                assert n_ml_seeds >= n_ml_seeds_cov

                derived_seeds: Set[pathlib.Path] = set()
                for ml_seed in ml_seed_list:
                    seed_id = get_seed_id(ml_seed.name)
                    new_seeds = find_descendants(ml_seed.parent, seed_id)
                    derived_seeds.update(new_seeds)
                n_ml_derived = len(derived_seeds)
                assert n_ml_derived <= n_seeds

                n_ml_seeds_trials.append(n_ml_seeds)
                perc_ml_seeds_trials.append(n_ml_seeds / n_seeds * 100)
                n_ml_seeds_cov_trials.append(n_ml_seeds_cov)
                n_ml_derived_trials.append(n_ml_derived / n_seeds * 100)
            stats[target.name] = [
                np.mean(n_ml_seeds_trials),
                np.mean(perc_ml_seeds_trials),
                np.mean(n_ml_seeds_cov_trials),
                np.mean(n_ml_derived_trials),
            ]
    stats_dict = {
        "index": list(stats.keys()),
        "index_names": ["target"],
        "columns": [
            "#ML seeds",
            "%ML seeds",
            "#ML seeds with cov",
            "%ML derived seeds",
        ],
        "column_names": ["metrics"],
        "data": list(stats.values()),
    }
    stats_pd = pd.DataFrame.from_dict(stats_dict, orient="tight")
    print(stats_pd.round(2))


if __name__ == "__main__":
    main()
