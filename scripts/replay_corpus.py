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
Script for replaying an AFL++ corpus to an instrumented target binary in order to
compute a plottable coverage data file.
"""
import argparse
import logging
import pathlib
import subprocess
import sys
from typing import Set

from neuzzpp.preprocess import CoverageBuilder
from neuzzpp.utils import get_timestamp_millis_from_filename

# Configure logger - console
logger = logging.getLogger("neuzzpp")
logger.setLevel(logging.INFO)
console_logger = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_logger.setFormatter(log_formatter)
logger.addHandler(console_logger)

parser = argparse.ArgumentParser()
parser.add_argument("input", help="path to input corpus", type=str)
parser.add_argument("output", help="path and name of the output plot file", type=str)
parser.add_argument(
    "target",
    help="target program and arguments",
    type=str,
    nargs=argparse.REMAINDER,
    metavar="target [target_args]",
)
args = parser.parse_args()

target_with_args = args.target
seeds_path = pathlib.Path(args.input)
seed_list = [seed for seed in seeds_path.glob("*") if seed.is_file() and seed.name != ".cur_input"]
# Order by timestamp in filename
seed_list = sorted(seed_list, key=lambda f: get_timestamp_millis_from_filename(f.name))

out_file = open(args.output, "w")
out_file.write("# relative_time, edges_found, test_case\n")

all_edges: Set[int] = set()
out: bytes
cov_tool = CoverageBuilder(target_with_args)

for seed in seed_list:
    try:
        command = cov_tool.get_command_for_seed(seed)
        out = subprocess.check_output(command, timeout=60.0)

        edges_curr_seed: Set[int] = set()
        for line in out.splitlines():
            edge = int(line.split(b":")[0])
            if edge not in all_edges:
                all_edges.add(edge)
        out_file.write(
            f'{int(get_timestamp_millis_from_filename(seed.name) / 1000)}, {len(all_edges)}, "{seed.name}"\n'
        )
    except subprocess.CalledProcessError as err:
        logger.error(f"Bitmap extraction failed: {err}")


out_file.close()
