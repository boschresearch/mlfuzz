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
for d in */ ; do for file in ./$d/NEUZZPP/*/default/docker.log; do tac $file | grep -Pom1 'val_prc: (0.\d*)' | awk -F':' '{ print $2}' ;  done | awk -v d=$d '{s+=$1; count++} END {print d " | " s/count " | " count " trials " }'; done
