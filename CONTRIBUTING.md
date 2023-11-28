# Adding a fuzzer

To introduce a new fuzzer to MLFuzz, follow the four steps below.

## Add a run script

* Create a new folder under `fuzzers` named following the naming convention `<fuzzer_name>_experiments`.
* There, create a Python script that can run the new fuzzer inside the Docker container (follow the example of any other fuzzer in MLFuzz).

## Patch the code of the fuzzer

This step is optional and aims to adapt the fuzzer to MLFuzz experimental practices.
Typical patches include:

* Create an option to fix the seed of the random number generator used by the fuzzer (most often, option `-s`). This aims to ensure experiment reproducibility.
* Adding sanitizers.
* Porting fuzzers to newer versions of their dependencies (e.g., when old ones are discontinued).

Instructions for creating a code patch:

* On a clean clone of the fuzzer to be integrated, make the desired code changes to the fuzzer sources.
* Build and test the modified fuzzer.
* Once the changes are validated, create code patches for all the patched files:

      git diff -- {filename} > {filename}_{change_name}.patch

* Include all the generated patch files in the folder of your new fuzzer in MLFuzz.

## Change the `Dockerfile` to clone and build the new fuzzer

For this, edit the `Dockerfile` at the root of the project.
If you created a code patch at the previous step, do not forget to copy and apply the patche to the fuzzer before building it in the `Dockerfile`.

      patch {filename} < {filename}_{change_name}.patch

## Add new fuzzer to fuzzers list

Change `scripts/run_experiments.py` and `scripts/experiment_config.yaml.default` to define the name of the new fuzzer and the binaries it will operate on.

# Adding a target program

The following steps provide some guidelines about adding new target programs.
All content regarding targets is defined in the `benchmarks` folder.

## Update Dockerfile

Update `benchmarks/Dockerfile` if the new target needs specific packages to be installed.

## Add build script

Create a new Python script in `benchmarks/` that fetches the sources and builds the new target.
Include there are seed corpus that is available.
Use examples from existing targets for guidance.

## Update Makefile

Update `benchmarks/Makefile` to call the previously created Python script to build the new target inside the Docker container.

## Add target to experiment configuration

Update `scripts/experiment_config.yaml.default` to add the name of the new target.
