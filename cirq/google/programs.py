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
import json
from typing import Dict, Iterable, Sequence, Tuple, TYPE_CHECKING, cast

import numpy as np

from cirq import ops, devices
from cirq.google import xmon_gates
from cirq.google.xmon_device import XmonDevice
from cirq.schedules import Schedule, ScheduledOperation
from cirq.value import Timestamp

if TYPE_CHECKING:
    from typing import Optional  # pylint: disable=unused-import


def gate_to_proto_dict(gate: ops.Gate,
                       qubits: Tuple[ops.QubitId, ...]) -> Dict:
    if isinstance(gate, ops.MeasurementGate):
        return _measure_to_proto_dict(gate, qubits)

    if isinstance(gate, ops.XPowGate):
        if len(qubits) != 1:
            # coverage: ignore
            raise ValueError('Wrong number of qubits.')
        return _x_to_proto_dict(gate, qubits[0])

    if isinstance(gate, ops.YPowGate):
        if len(qubits) != 1:
            # coverage: ignore
            raise ValueError('Wrong number of qubits.')
        return _y_to_proto_dict(gate, qubits[0])

    if isinstance(gate, ops.PhasedXPowGate):
        if len(qubits) != 1:
            # coverage: ignore
            raise ValueError('Wrong number of qubits.')
        return _phased_x_to_proto_dict(gate, qubits[0])

    if isinstance(gate, ops.ZPowGate):
        if len(qubits) != 1:
            # coverage: ignore
            raise ValueError('Wrong number of qubits.')
        return _z_to_proto_dict(gate, qubits[0])

    if isinstance(gate, ops.CZPowGate):
        if len(qubits) != 2:
            # coverage: ignore
            raise ValueError('Wrong number of qubits.')
        return _cz_to_proto_dict(gate, *qubits)

    raise ValueError("Don't know how to serialize this gate: {!r}".format(gate))


def _x_to_proto_dict(gate: ops.XPowGate, q: ops.QubitId) -> Dict:
    exp_w = {
        'target': cast(devices.GridQubit, q).to_proto_dict(),
        'axis_half_turns':
            xmon_gates._parameterized_value_to_proto_dict(0),
        'half_turns': xmon_gates._parameterized_value_to_proto_dict(
            gate.exponent)
    }
    return {'exp_w': exp_w}


def _y_to_proto_dict(gate: ops.YPowGate, q: ops.QubitId) -> Dict:
    exp_w = {
        'target': cast(devices.GridQubit, q).to_proto_dict(),
        'axis_half_turns':
            xmon_gates._parameterized_value_to_proto_dict(0.5),
        'half_turns': xmon_gates._parameterized_value_to_proto_dict(
            gate.exponent)
    }
    return {'exp_w': exp_w}


def _phased_x_to_proto_dict(gate: ops.PhasedXPowGate,
                            q: ops.QubitId) -> Dict:
    exp_w = {
        'target': cast(devices.GridQubit, q).to_proto_dict(),
        'axis_half_turns':
            xmon_gates._parameterized_value_to_proto_dict(
                gate.phase_exponent),
        'half_turns': xmon_gates._parameterized_value_to_proto_dict(
            gate.exponent)
    }
    return {'exp_w': exp_w}


def _z_to_proto_dict(gate: ops.ZPowGate, q: ops.QubitId) -> Dict:
    exp_z = {
        'target': cast(devices.GridQubit, q).to_proto_dict(),
        'half_turns': xmon_gates._parameterized_value_to_proto_dict(
            gate.exponent),
    }
    return {'exp_z': exp_z}


def _cz_to_proto_dict(gate: ops.CZPowGate,
                      p: ops.QubitId,
                      q: ops.QubitId) -> Dict:
    exp_11 = {
        'target1': cast(devices.GridQubit, p).to_proto_dict(),
        'target2': cast(devices.GridQubit, q).to_proto_dict(),
        'half_turns': xmon_gates._parameterized_value_to_proto_dict(
            gate.exponent)
    }
    return {'exp_11': exp_11}


def _measure_to_proto_dict(gate: ops.MeasurementGate,
                           qubits: Sequence[ops.QubitId]):
    if len(qubits) == 0:
        raise ValueError('Measurement gate on no qubits.')
    if gate.invert_mask and len(gate.invert_mask) != len(qubits):
        raise ValueError('Measurement gate had invert mask of length '
                         'different than number of qubits it acts on.')
    measurement = {
        'targets': [cast(devices.GridQubit, q).to_proto_dict() for q in qubits],
        'key': gate.key,
    }
    if gate.invert_mask:
        measurement['invert_mask'] = [json.dumps(x) for x in
                                      gate.invert_mask]
    return {'measurement': measurement}


def schedule_to_proto_dicts(schedule: Schedule) -> Iterable[Dict]:
    """Convert a schedule into an iterable of proto dictionaries.

    Args:
        schedule: The schedule to convert to a proto dict. Must contain only
            gates that can be cast to xmon gates.

    Yields:
        A proto dictionary corresponding to an Operation proto.
    """
    last_time_picos = None  # type: Optional[int]
    for so in schedule.scheduled_operations:
        op = gate_to_proto_dict(
            cast(ops.GateOperation, so.operation).gate,
            so.operation.qubits)
        time_picos = so.time.raw_picos()
        if last_time_picos is None:
            op['incremental_delay_picoseconds'] = time_picos
        else:
            op['incremental_delay_picoseconds'] = time_picos - last_time_picos
        last_time_picos = time_picos
        yield op


def schedule_from_proto_dicts(
        device: XmonDevice,
        ops: Iterable[Dict],
) -> Schedule:
    """Convert proto dictionaries into a Schedule for the given device."""
    scheduled_ops = []
    last_time_picos = 0
    for op in ops:
        delay_picos = 0
        if 'incremental_delay_picoseconds' in op:
            delay_picos = op['incremental_delay_picoseconds']
        time_picos = last_time_picos + delay_picos
        last_time_picos = time_picos
        xmon_op = xmon_gates.xmon_op_from_proto_dict(op)
        scheduled_ops.append(ScheduledOperation.op_at_on(
            operation=xmon_op,
            time=Timestamp(picos=time_picos),
            device=device,
        ))
    return Schedule(device, scheduled_ops)


def pack_results(measurements: Sequence[Tuple[str, np.ndarray]]) -> bytes:
    """Pack measurement results into a byte string.

    Args:
        measurements: A sequence of tuples, one for each measurement, consisting
            of a string key and an array of boolean data. The data should be
            a 2-D array indexed by (repetition, qubit_index). All data for all
            measurements must have the same number of repetitions.

    Returns:
        Packed bytes, as described in the unpack_results docstring below.

    Raises:
        ValueError if the measurement data do not have the compatible shapes.
    """
    if not measurements:
        return b''

    shapes = [(key, np.shape(data)) for key, data in measurements]
    if not all(len(shape) == 2 for _, shape in shapes):
        raise ValueError("Expected 2-D data: shapes={}".format(shapes))

    reps = shapes[0][1][0]
    if not all(shape[0] == reps for _, shape in shapes):
        raise ValueError(
            "Expected same reps for all keys: shapes={}".format(shapes))

    bits = np.hstack(np.asarray(data, dtype=bool) for _, data in measurements)
    bits = bits.reshape(-1)

    # Pad length to multiple of 8 if needed.
    remainder = len(bits) % 8
    if remainder:
        bits = np.pad(bits, (0, 8 - remainder), 'constant')

    # Pack in little-endian bit order.
    bits = bits.reshape((-1, 8))[:, ::-1]
    byte_arr = np.packbits(bits, axis=1).reshape(-1)

    return byte_arr.tobytes()


def unpack_results(
        data: bytes,
        repetitions: int,
        key_sizes: Sequence[Tuple[str, int]]
) -> Dict[str, np.ndarray]:
    """Unpack data from a bitstring into individual measurement results.

    Args:
        data: Packed measurement results, in the form <rep0><rep1>...
            where each repetition is <key0_0>..<key0_{size0-1}><key1_0>...
            with bits packed in little-endian order in each byte.
        repetitions: number of repetitions.
        key_sizes: Keys and sizes of the measurements in the data.

    Returns:
        Dict mapping measurement key to a 2D array of boolean results. Each
        array has shape (repetitions, size) with size for that measurement.
    """
    bits_per_rep = sum(size for _, size in key_sizes)
    total_bits = repetitions * bits_per_rep

    byte_arr = np.frombuffer(data, dtype='uint8').reshape((len(data), 1))
    bits = np.unpackbits(byte_arr, axis=1)[:, ::-1].reshape(-1).astype(bool)
    bits = bits[:total_bits].reshape((repetitions, bits_per_rep))

    results = {}
    ofs = 0
    for key, size in key_sizes:
        results[key] = bits[:, ofs:ofs + size]
        ofs += size

    return results
