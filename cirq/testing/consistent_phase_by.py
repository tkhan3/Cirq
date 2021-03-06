# Copyright 2018 The Cirq Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any

import numpy as np

from cirq import protocols, linalg
from cirq.testing import lin_alg_utils


def assert_phase_by_is_consistent_with_unitary(val: Any):
    """Uses `val._unitary_` to check `val._phase_by_`'s behavior."""

    original = protocols.unitary(val)
    qubit_count = len(original).bit_length() - 1
    original.shape = (2, 2) * qubit_count

    at_least_one_qubit_is_phaseable = False
    for t in [0.125, -0.25, 1]:
        p = 1j**(t*4)
        for i in range(qubit_count):
            phased = protocols.phase_by(val, t, i, default=None)
            if phased is None:
                continue
            at_least_one_qubit_is_phaseable = True

            actual = protocols.unitary(phased)
            actual.shape = (2, 2) * qubit_count

            expected = np.array(original)
            s = linalg.slice_for_qubits_equal_to([i], 1)
            expected[s] *= p
            s = linalg.slice_for_qubits_equal_to([qubit_count + i], 1)
            expected[s] *= np.conj(p)

            lin_alg_utils.assert_allclose_up_to_global_phase(
                actual,
                expected,
                atol=1e-8,
                err_msg='Phased unitary was incorrect for index #{}'.format(i))

    assert at_least_one_qubit_is_phaseable, (
        '_phase_by_ is consistent with _unitary_, but only because the given '
        'value was not phaseable.')
