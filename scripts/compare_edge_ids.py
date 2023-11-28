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
This intersects the found edges from a fuzzing experiment folder.

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
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set

from neuzzpp.preprocess import create_path_coverage_bitmap

# Define supported fuzzers - AFLPP based fuzzers for now only
Fuzzer = Enum("Fuzzer", "AFLPP HAVOC NEUZZ NEUZZPP PREFUZZ")
fuzzers = [
    Fuzzer.AFLPP,
    Fuzzer.NEUZZPP,
    Fuzzer.NEUZZ,
    Fuzzer.PREFUZZ,
]

# Configure console logger
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("neuzzpp")


def get_edge_ids_for_corpus(corpus_path: pathlib.Path, target_with_args: List[str]) -> Set[int]:
    """
    Extracts a set of edge IDs that the given corpus triggers on the given target

    Args:
        corpus_path : The path to the corpus
        target_with_args : The target binary with arguments

    Returns:
        The set of triggered edge IDs.
    """

    seed_list = [seed for seed in corpus_path.glob("id*")]

    cov_bitmap: Dict[pathlib.Path, Optional[Set[int]]] = create_path_coverage_bitmap(
        target_with_args, seed_list
    )
    all_edges = set.union(*cov_bitmap.values())

    return all_edges


def compute_edge_intersections_for_experiment(
    experiments_folder: pathlib.Path, binaries_folder: pathlib.Path
) -> Dict[str, Dict[Fuzzer, Dict[int, int]]]:
    """
    Extract coverage information from an experiment into a Pandas dataframe.

    Assumptions:
      * Coverage files are called `replayed_plot_data`.
      * An experiment is structured as:
          <exp_name>/<target>/<fuzzer>/trial-<index>/<fuzzer_output>
        or
          <exp_name>/<target>/<fuzzer>/trial-<index>/default/<fuzzer_output>.
      * The names of the plot data columns used for computations are "# relative_time"
        and "edges_found".

    Args:
        experiments_folder: Experiment folder structured as specified above.
        binaries_folder: Path to fuzzing targets.
    Returns
        A dictionary of edge data per target.
    """

    edges_per_target: Dict[str, Dict[Fuzzer, Dict[int, int]]] = {}
    # Walk folders and extract edge ids for each fuzzer and target
    for target in experiments_folder.glob("*"):
        cumulated_edges: Dict[Fuzzer, Dict[int, int]] = {}
        for fuzzer in fuzzers:
            fuzzer_exp_path = target.joinpath(fuzzer.name)
            cumulated_edges[fuzzer] = {}
            trial_count = 0
            for trial in fuzzer_exp_path.glob("trial-*"):
                corpus = list(trial.glob("**/queue"))
                if len(corpus) != 1:
                    logger.warning(f"Unexpected folder structure in {trial.absolute()}")
                    break

                target_with_args = binaries_folder / f"{target.name}.aflpp"

                logger.info(f"Investigating Corpus {corpus[0]} on {target_with_args}")

                edge_ids = get_edge_ids_for_corpus(corpus[0], [str(target_with_args)])
                trial_count += 1
                for edge_id in edge_ids:
                    if edge_id not in cumulated_edges[fuzzer]:
                        cumulated_edges[fuzzer][edge_id] = 1  # seen edge for the first time
                    else:
                        cumulated_edges[fuzzer][edge_id] += 1  # increment edge counter
            logger.info(f"Got {trial_count} trials for {fuzzer.name}!")

        edges_per_target[target.name] = cumulated_edges

    return edges_per_target


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("results_folder", help="output folder from an experiment", type=str)
    parser.add_argument("binaries_folder", help="folder containing target binaries", type=str)
    args = parser.parse_args(argv[1:])

    edges_per_target = compute_edge_intersections_for_experiment(
        pathlib.Path(args.results_folder).expanduser(),
        pathlib.Path(args.binaries_folder).expanduser(),
    )

    print(
        "| Target | #Edges AFL++ | #Edges Neuzz++ | Union | AFL++ excl. "
        "| Neuzz++ excl. | Neuzz - AFL++ | PreFuzz - AFL++ | Neuzz - Neuzz++ | PreFuzz - Neuzz++ | "
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ")

    for target in edges_per_target.keys():

        cumulated_edges = edges_per_target[target]
        unified_edges = set(cumulated_edges[Fuzzer.AFLPP].keys()).union(
            cumulated_edges[Fuzzer.NEUZZPP].keys()
        )
        aflpp_edges = cumulated_edges[Fuzzer.AFLPP].keys()
        neuzpp_edges = cumulated_edges[Fuzzer.NEUZZPP].keys()

        # Print intersection and subtractions
        print(
            f"| {target} | {len(aflpp_edges)} "
            f"| {len(neuzpp_edges)} "
            f"| {len(unified_edges)} "
            f"| {len(aflpp_edges - neuzpp_edges)} "
            f"| {len(neuzpp_edges - aflpp_edges)} "
            f"| {len(cumulated_edges[Fuzzer.NEUZZ].keys() - aflpp_edges)} "
            f"| {len(cumulated_edges[Fuzzer.PREFUZZ].keys() - aflpp_edges)} "
            f"| {len(cumulated_edges[Fuzzer.NEUZZ].keys() - neuzpp_edges)} "
            f"| {len(cumulated_edges[Fuzzer.PREFUZZ].keys() - neuzpp_edges)} | "
        )


if __name__ == "__main__":
    main()
