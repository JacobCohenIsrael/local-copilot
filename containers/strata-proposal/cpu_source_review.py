"""Evidence qualification for ONE CPU-only build review; no policy activation."""
import hashlib
import json
from pathlib import Path

import build_policy_review as policy
import stage_build_tools as tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / '.runtime'
READER_SHA = 'e8a3db7155b4ef177344d12bc1326f02f5da16ea9bab0a71066a97bb0c67b90d'
REFERENCE_SHA = 'c4d9273b43543ada9e79f811293ef54961c88f48e81817c13e8a6e0609adbafe'
PROBE_SHA = '8f0eb0b09af759c061603c8967e1306206a6a6c3e916649d2471b197e20542b0'
PROBE = ROOT / 'compiler-guard/99766c3642bd4773af3121e5595e3631/probe-result.json'
REFERENCE = ROOT / 'cpu-source-review/references/AsusACPI.cs.txt'
ARMOURY = [78, 73, 67, 82, 93, 95]  # Direct owner report, not timestamp-paired samples.
LIMITATION = 'Firmware refresh latency and calibration are not independently guaranteed; acceptance is for one monitored CPU-only build, never model runtime.'


def bounded(path, maximum):
    tools.plain(path)
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('CPU evidence exceeds budget')
    return raw


def report():
    raw = bounded(PROBE, 65536)
    probe = json.loads(raw)
    reference = bounded(REFERENCE, 131072)
    if (hashlib.sha256(raw).hexdigest() != PROBE_SHA or tools.sha(HERE / 'cpu_reader.ps1') != READER_SHA or
            hashlib.sha256(reference).hexdigest() != REFERENCE_SHA or
            b'public const int Temp_CPU = 0x00120094;' not in reference or
            b'return BitConverter.ToInt32(status, 0) - 65536;' not in reference):
        raise ValueError('Reviewed reader/reference identity changed')
    if (probe.get('version') != 1 or probe.get('status') != 'TEN_SAMPLES_OBSERVED_NOT_CERTIFIED' or
            probe.get('synthetic') is not False or probe.get('readerSha256') != READER_SHA or
            probe.get('validatedCpuSensor') is not False or probe.get('cpuThermalThrottling') is not None or
            probe.get('workloadStarted') is not False or probe.get('readerStopped') is not True):
        raise ValueError('CPU observation provenance/completion invalid')
    rows = probe.get('samples')
    if not isinstance(rows, list) or len(rows) != 10:
        raise ValueError('Expected the ten-sample CPU observation')
    for sequence, row in enumerate(rows, 1):
        if (type(row.get('sequence')) is not int or row['sequence'] != sequence or
                row.get('synthetic') is not False or row.get('source') != 'ASUS DSTS 0x00120094' or
                row.get('error') is not None or row.get('validatedCpuSensor') is not False or
                row.get('cpuThermalThrottling') is not None or
                not policy.finite(row.get('cpuTemperatureC')) or not 0 < row['cpuTemperatureC'] <= 125 or
                not policy.finite(row.get('recordedAtUnix')) or
                not policy.finite(row.get('querySeconds')) or not 0 <= row['querySeconds'] <= 1):
            raise ValueError('CPU observation contains invalid/unreviewed frame')
    intervals = [b['recordedAtUnix'] - a['recordedAtUnix'] for a, b in zip(rows, rows[1:])]
    temperatures = [r['cpuTemperatureC'] for r in rows]
    if (not all(0 < delta <= 2.5 for delta in intervals) or len(set(temperatures)) < 2 or
            max(min(temperatures), min(ARMOURY)) > min(max(temperatures), max(ARMOURY))):
        raise ValueError('CPU update/comparison evidence fails review criteria')
    return {'version': 1, 'status': 'QUALIFIED_FOR_OWNER_REVIEW_NOT_ACTIVATED',
            'scope': 'one-cpu-only-linux-compile-no-engine-execution',
            'readerSha256': READER_SHA, 'probeSha256': hashlib.sha256(raw).hexdigest(),
            'referenceSha256': REFERENCE_SHA,
            'referenceUrl': 'https://github.com/seerge/g-helper/blob/main/app/AsusACPI.cs',
            'checks': {'endpointAndDecodeCorroborated': True, 'realPassiveReadAccess': True,
                       'changingValuesObserved': True, 'boundedDeliveryObserved': True,
                       'manualRangeComparisonCompleted': True, 'readerStopConfirmed': True},
            'sampleCount': 10, 'observedTemperaturesC': temperatures, 'ownerArmouryValuesC': ARMOURY,
            'observedIntervalsSeconds': [round(n, 6) for n in intervals],
            'maxObservedQuerySeconds': max(r['querySeconds'] for r in rows),
            'limitations': [LIMITATION, 'No paired timestamps: no calibrated offset is inferred.',
                            'The short observation is not sustained coverage or a ten-second cool baseline.'],
            'requiresExplicitSourceAcceptance': True, 'validatedCpuSensor': False,
            'buildEnabled': False, 'modelLaunchEnabled': False}
