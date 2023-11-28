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
This script analyzes files in the crashes folder, executes them on the target binary
and identifies unique crashes upon a stacktrace.

The following structure is assumed about the experiment folder:
  <exp_name>/<target>/<fuzzer>/trial-<index>/<fuzzer_output>
or
  <exp_name>/<target>/<fuzzer>/trial-<index>/default/<fuzzer_output>
These are compatible with output from AFL, AFL++ and other fuzzers based on them.
"""
import argparse
import logging
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Sequence, Set, Tuple

from pygdbmi.gdbcontroller import GdbController

# Define supported fuzzers
Fuzzer = Enum("Fuzzer", "AFL AFLPP HAVOC NEUZZ NEUZZPP PREFUZZ")
fuzzers = [Fuzzer.AFL, Fuzzer.AFLPP, Fuzzer.HAVOC, Fuzzer.NEUZZ, Fuzzer.NEUZZPP, Fuzzer.PREFUZZ]


# Configure console logger
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("neuzzpp")


def test_one_input(binary_file: pathlib.Path, input_file: pathlib.Path) -> str:
    """
    Executes the provided input in the target binary and extracts the stack trace
    if the execution ended with a signal.
    The signal and the addresses of all stack frames are concatenated and returned as string.
    If no signal was emitted, a empty string is returned.

    Args:
        binary_file: path to the target binary
        input_file:  path to the input file to test

    Returns:
        str: returned signal and stack frame addresses or empty string
    """

    try:
        subprocess.check_output([binary_file, input_file])
        # If we reach this point, there is no error -> no crash :)
        return ""
    except subprocess.CalledProcessError as e:

        # Start gdb process
        # Seems like the extra second is use
        # We set additional output sec to a low number
        # And sleep later on manually for overall speedup
        gdbmi = GdbController(time_to_check_for_additional_output_sec=0.01)

        # Load binary and get structured response
        response = gdbmi.write(f"-file-exec-file {binary_file} ")

        # We don't want ASLR :)
        response = gdbmi.write("set disable-randomization on")

        # Set args to crashing input
        response = gdbmi.write(f"set args {input_file}")

        # Set breakpoint on exit function and syscall to
        # interrupt execution on crash
        response = gdbmi.write("set breakpoint pending on")
        response = gdbmi.write("br _exit")
        response = gdbmi.write("br exit")
        response = gdbmi.write("catch syscall 60")
        response = gdbmi.write("catch syscall 231")

        # run
        response = gdbmi.write("run")

        # Get signal name and stack frame addresses
        response += gdbmi.write("-stack-list-frames")

        # Wait till desired messages from GDB arrive
        # Unfortunately the gdbmi package can not block until all
        # messages have arrived, so the only way is to wait
        # for a fixed amount of time.
        # We do some active checking to avoid waiting longer than
        # we need -> speedup
        while "done" not in str(response) and "stack" not in str(response):
            time.sleep(0.1)
            response += gdbmi.write("continue")

        stacktrace = ""
        for message in response:
            if message["message"] == "stopped":
                # Check if signal was raised
                if "signal-name" in message["payload"]:
                    stacktrace = message["payload"]["signal-name"]
                else:
                    # We catch 'exit' in gdb directly to be
                    # able to obtain a stacktrace before
                    # the program exits. The downside is that
                    # we don't get an exit code from gdb back at
                    # this point, but we still have the one from
                    # the dry run without gdb
                    stacktrace = f"EXIT_{str(e.returncode)}"

            # this should come after the 'stopped' message
            elif (
                message["message"] == "done" and message["payload"] and message["payload"]["stack"]
            ):
                # Append stack trace, if available
                for frame in message["payload"]["stack"]:
                    stacktrace += " " + frame["addr"]

        # Shutdown GDB
        gdbmi.exit()

        return stacktrace


def test_crashes_folder(
    binary_file: pathlib.Path, crashes_folder: pathlib.Path
) -> Tuple[int, Set[str]]:
    """
    Tests all files in the given folder on the provided executable.
    Deduplicates eventual crashes and returns the number of tested
    files and a set of unique error codes.

    Args:
        binary_file: Path to the executable.
        crashes_folder: Path to folder with inputs to test.

    Returns: The number of tested files and a set of unique error codes.
    """

    unique_errors: Set[str] = set()
    n_files = 0
    for input_ in crashes_folder.glob("id*"):
        logger.info(f"Test {input_} on {binary_file.name}")
        error = test_one_input(binary_file, input_)
        n_files += 1
        if error != "":
            logger.info(error)
            unique_errors.add(error)
    return n_files, unique_errors


@dataclass
class FuzzerCrashStats:

    # The number of crashes reported by the fuzzer in all trails
    n_reported_crashes: int

    # The number of unique crashes from all trials
    n_unique_crashes: int

    # The number of crashes exclusively found by this fuzzer
    n_exclusive_crashes: int

    def __str__(self):
        return f"{self.n_reported_crashes} / {self.n_unique_crashes} / {self.n_exclusive_crashes}"


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("results_folder", help="output folder from an experiment", type=str)
    parser.add_argument("binaries_folder", help="folder containing target binaries", type=str)
    args = parser.parse_args(argv[1:])

    exp_folder = pathlib.Path(args.results_folder)
    bin_folder = pathlib.Path(args.binaries_folder)

    # We need to disable leak sanitizer when using GDB.
    # Additionally, we ask ASAN to abort execution on an error
    os.environ["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1"

    data: Dict[str, Dict[Fuzzer, FuzzerCrashStats]] = {}

    # Walk folders and extract edge ids for each fuzzer and target
    for target in sorted(exp_folder.glob("*")):

        data[target.name] = {}
        # For collecting all found crashes for this target
        # Actually, a custom struct would be cool here
        unique_target_error_codes: Dict[Fuzzer, Set[str]] = {}

        for fuzzer in fuzzers:
            fuzzer_exp_path = target.joinpath(fuzzer.name)

            # For collecting all found crashes for this fuzzer+target
            unique_target_error_codes[fuzzer] = set()
            n_avg_crash_files = 0
            trial_count = 0
            for trial in fuzzer_exp_path.glob("trial-*"):

                crashes = list(trial.glob("**/crashes"))
                if len(crashes) != 1:
                    logger.warning(f"Unexpected folder structure in {trial.absolute()}")
                    break

                # Get correct binary file path
                if fuzzer in [Fuzzer.AFLPP, Fuzzer.NEUZZPP]:
                    binary_file_path = bin_folder / f"{target.name}.aflpp"
                else:
                    binary_file_path = bin_folder / f"{target.name}.afl"

                n_files, unique_error_codes = test_crashes_folder(binary_file_path, crashes[0])
                n_avg_crash_files += n_files
                logger.info(
                    f"{fuzzer} trial {trial_count} found "
                    f"{len(unique_error_codes)} unique crashing inputs"
                )
                unique_target_error_codes[fuzzer].update(unique_error_codes)
                trial_count += 1
            if trial_count > 0:
                data[target.name][fuzzer] = FuzzerCrashStats(
                    n_avg_crash_files, len(unique_target_error_codes[fuzzer]), 0
                )
            else:
                data[target.name][fuzzer] = FuzzerCrashStats(0, 0, 0)

        for fuzzer_base in fuzzers:
            exclusive_target_error_codes = unique_target_error_codes[fuzzer_base]

            for fuzzer in set(fuzzers) - set(fuzzer_base):
                exclusive_target_error_codes -= unique_target_error_codes[fuzzer]

            logger.info(
                f"Fuzzer {fuzzer_base} found {len(unique_target_error_codes[fuzzer_base])} "
                f"unique crashing inputs from which {len(exclusive_target_error_codes)} "
                f"are exclusive"
            )
            data[target.name][fuzzer_base].n_exclusive_crashes = len(exclusive_target_error_codes)

    # Print table in latex style
    # One day I will learn how to put this into pandas
    print("        & ", end="")
    for fuzzer in fuzzers:
        print(f"{fuzzer}    & ", end="")
    print("     \\\\")

    for target_name in sorted(data.keys()):
        print(f"{target_name}    & ", end="")
        for fuzzer in fuzzers:
            print(f"{data[target_name][fuzzer]}    & ", end="")
        print("     \\\\")


if __name__ == "__main__":
    main()
