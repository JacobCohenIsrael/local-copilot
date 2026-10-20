"""Offline RAM-stop boundaries, scope isolation and refusal before execution."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import coding_task_2_ram30 as scope
import runtime_safety as safety
from test_runtime import cpu, gpu


class Ram30Tests(unittest.TestCase):
    def test_saved_crossing_passes_new_stop_exact_boundary_trips_and_latches(self):
        self.assertEqual(safety.POLICY['ramStopMiB'], 28672)
        with patch.object(safety, 'POLICY', {**safety.POLICY, 'ramStopMiB': 30720}):
            for used, expected in [(29090.76953125, None), (30719.99, None),
                                   (30720, 'HOST_RAM_HIGH'), (30721, 'HOST_RAM_HIGH')]:
                gate = safety.Gate()
                gate.model_started = 0
                admitted = gate.observe(cpu(), gpu(ramUsedMiB=used), now=0, unix=1000, controller_age=0)
                self.assertEqual(gate.fault, expected)
                self.assertEqual(admitted, expected is None)
                if expected:
                    self.assertFalse(gate.observe(cpu(2,1001), gpu(1001), now=1, unix=1001, controller_age=0))
                    self.assertEqual(gate.fault, expected)

    def test_other_emergency_stops_still_apply_with_30gib_policy(self):
        with patch.object(safety, 'POLICY', {**safety.POLICY, 'ramStopMiB': 30720}):
            for c, g, age, fault in [({'cpuTemperatureC':97},{},0,'CPU_HOT'),
                    ({},{'gpuTemperatureC':75},0,'GPU_HOT'),
                    ({},{'gpuPowerW':100},0,'GPU_POWER_HIGH'),
                    ({},{'vramUsedMiB':14336},0,'VRAM_HIGH'),
                    ({},{},2.51,'CONTROLLER_LEASE_EXPIRED'),
                    ({},{'recordedAtUnix':996},0,'TELEMETRY_STALE_OR_MISSING')]:
                gate = safety.Gate()
                gate.observe(cpu(**c), gpu(**g), now=0, unix=1000, controller_age=age)
                self.assertEqual(gate.fault, fault)

    def test_only_authorized_ram_stop_changes_and_readiness_stays_absent(self):
        base = scope.p.read(scope.REJECTED / 'review.json', 131072)
        root = scope.REPO / '.runtime/ram30-offline-tests'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs = Path(temporary) / 'input'
            inputs.mkdir()
            for path in (Path(base['packageDirectory']) / 'input').iterdir():
                (inputs / path.name).write_bytes(path.read_bytes())
            packet = {**base, 'packageDirectory': temporary,
                      'policy': {**base['policy'], 'ramStopMiB': 30720}}
            with patch.object(scope.p, 'INPUT_SCRIPTS', dict(scope.timing.SCRIPTS)), \
                 patch.object(scope.task, 'WORKER_HELPERS', dict(scope.HELPERS)), patch.object(scope.task, 'check_task'):
                scope.same_limits(packet)
                for area, key, value in [('policy','ramStopMiB',30721), ('policy','ramStopMiB',28672),
                        ('policy','cpuStopC',98), ('policy','startupTargetsWarningsOnly',False),
                        ('requestTimingChange','hardRequestDeadlineSeconds',151),
                        ('configuration','engine_silence_s',76), ('request','max_tokens',33),
                        ('request','messages',[]), ('codingTask','modelCalls',2)]:
                    changed = copy.deepcopy(packet)
                    changed[area][key] = value
                    with self.subTest(area=area,key=key), self.assertRaises(ValueError): scope.same_limits(changed)
                with self.assertRaisesRegex(ValueError, 'RAM_READINESS_DEFERRED'):
                    scope.same_limits({**packet, 'hostRamReadiness': {}})

    def test_controller_watchdog_and_cli_use_same_scope_without_readiness_or_old_approvals(self):
        script = '''
import sys,runpy
from unittest.mock import patch
import coding_task_2_ram30 as s
old_policy = s.p.safety.POLICY
with patch.object(s.history, 'activate', side_effect=AssertionError('readiness activated')), \
     patch.object(s.history.readiness, 'read_once') as read, \
     patch.object(s.p.safety, 'snapshot') as sensors, \
     patch.object(s.task.coding.first_api.guard.base, 'Docker') as docker:
    s.activate()
    assert old_policy['ramStopMiB']==28672
    assert s.p.safety.POLICY=={**old_policy,'ramStopMiB':30720}
    assert s.p.APPROVAL.name=='coding-task-2-ram30-approval.json'
    assert s.task.coding.first_api.WATCH_ENTRYPOINT==s.Path(s.__file__).resolve()
    assert s.p.REQUEST==s.prior.REQUEST and s.p.config()['engine_silence_s']==75
    # The live RAM30 scope is now spent. Keep missing-decision coverage
    # independent of its preserved approval and worker evidence.
    s.p.APPROVAL=s.HERE/'missing-ram30-offline-decision.json'
    s.task.coding.WORKER=s.REPO/'.runtime/missing-ram30-offline-worker'
    assert not s.p.APPROVAL.exists()
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval allowed')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-useful-coding-task-ram30']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json','coding-task-2-compact-approval.json']:
        with patch.object(s.p,'APPROVAL',s.HERE/name),patch.object(s.p,'review',return_value=('b'*64,{})):
            try:s.p.authorize()
            except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
            else:raise AssertionError('spent approval reused')
    read.assert_not_called();sensors.assert_not_called();docker.assert_not_called()
    # Exercise the independent watch entry point with its live loop replaced.
    with patch.object(s.task.coding.first_api,'watch') as watch,patch.object(sys,'argv',[s.__file__,'--watch']):
        runpy.run_path(s.__file__,run_name='__main__')
        watch.assert_called_once()
        assert s.p.safety.POLICY['ramStopMiB']==30720
    read.assert_not_called();sensors.assert_not_called();docker.assert_not_called()
'''
        result = subprocess.run([sys.executable,'-B','-c',script], cwd=scope.HERE,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_preserved_host_ram_failure_and_deferred_snapshot_are_bound(self):
        self.assertFalse(scope.history.ram_fault_proof()['previousApprovalReused'])
        self.assertFalse(scope.deferred_proof(True)['readinessEnabled'])
        with patch.object(scope, 'DEFERRED_MANIFEST', '0'*64):
            with self.assertRaisesRegex(ValueError, 'DEFERRED_PREPARATION_CHANGED'): scope.deferred_proof()


if __name__ == '__main__': unittest.main()
