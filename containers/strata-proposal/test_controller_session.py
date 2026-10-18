import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import artifact_export as export
import build_guard as guard
import build_policy_review as policy
import build_preflight
import controller_session as controller
import offline_target
from test_artifact_export import archive, SHA


class Clock:
    value = 0

    def __call__(self):
        return self.value


class Docker:
    def __init__(self, target, clock):
        expected = json.loads(target.contract_json)
        self.clock, self.calls, self.unavailable = clock, [], False
        self.info = {'Id': target.container_id, 'Name': '/' + expected['name'],
                     'Config': {'Image': expected['image'], 'User': '65532:65532',
                                'Entrypoint': expected['entrypoint'], 'Cmd': expected['command'],
                                'WorkingDir': '/work', 'Env': ['NVIDIA_VISIBLE_DEVICES=void'],
                                'Labels': expected['labels']},
                     'HostConfig': {**expected['host'], 'RestartPolicy': {'Name': 'no'},
                                    'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'], 'IpcMode': 'private'},
                     'Mounts': [{'Type': 'bind', 'Source': source, 'Destination': dest, 'RW': rw}
                                for source, dest, rw in expected['binds']],
                     'State': {'Running': False, 'Status': 'created', 'ExitCode': 0, 'OOMKilled': False}}

    def inspect(self, _):
        if self.unavailable:
            raise RuntimeError('Simulated daemon outage')
        return self.info

    def call(self, *args, timeout):
        self.calls.append(args)
        self.clock.value += .01
        if self.unavailable:
            raise RuntimeError('Simulated daemon outage')
        if args[:2] == ('container', 'inspect'):
            if self.info is None:
                raise guard.base.subprocess.CalledProcessError(1, args, stderr='No such container')
            return json.dumps([self.info])
        if args[0] in ('stop', 'kill'):
            self.info['State'].update(Running=False, Status='exited', ExitCode=137)
        if args[0] == 'rm':
            self.info = None
        return ''


class ControllerSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.namespace = self.root / 'controller'
        self.directory = self.namespace / 'sessions' / ('1' * 32)
        self.directory.mkdir(parents=True)
        contract = {'name': 'synthetic-owned', 'image': guard.base.IMAGE,
                    'entrypoint': ['/usr/local/bin/python3'], 'command': ['fixed-synthetic-fixture'],
                    'labels': {'local-copilot.kind': 'test'}, 'host': offline_target.host_profile(fixture=True),
                    'binds': offline_target.binds([(self.directory / 'input', '/input')])}
        self.target = offline_target.Target('a' * 64, json.dumps(contract), 'b' * 64, SHA, synthetic=True)
        self.clock = Clock()
        self.docker = Docker(self.target, self.clock)
        self.session = controller.Session(self.namespace, self.directory, self.target, self.docker,
                                          clock=self.clock, unix=lambda: 1000 + self.clock())
        self.reserve = patch.object(export.tools, 'reserve')
        self.reserve.start()
        self.exports = patch.object(export, 'ROOT', self.root / 'exports')
        self.exports.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.reserve.stop)
        self.addCleanup(self.exports.stop)

    def frame(self, temperature=92):
        return policy.synthetic(int(self.clock() * 1000) + 1, self.clock(), cpuTemperatureC=temperature)

    def test_first_heartbeat_is_visible_only_after_its_byte_is_complete(self):
        target=self.directory/'atomic.pulse'
        original=Path.rename
        def rename(source,destination):
            self.assertEqual(source.read_bytes(),b'.')
            self.assertFalse(target.exists())
            self.assertEqual(destination,target)
            return original(source,destination)
        with patch.object(Path,'rename',rename):
            controller.pulse(target)
        self.assertEqual(target.read_bytes(),b'.')
        lease=controller.Pulse(target,clock=self.clock)
        self.assertEqual(lease.age(),0)
        self.clock.value=1
        controller.pulse(target)
        self.assertEqual(lease.age(),0)
        self.assertEqual(target.read_bytes(),b'..')

    def test_empty_existing_heartbeat_still_fails_instead_of_refreshing_lease(self):
        target=self.directory/'invalid.pulse'
        target.write_bytes(b'')
        lease=controller.Pulse(target,clock=self.clock)
        with self.assertRaisesRegex(ValueError,'invalid/regressed'):
            lease.age()
        self.assertEqual(target.read_bytes(),b'')

    def exporting(self):
        for second in range(11):
            self.clock.value = second
            self.session.poll(self.frame())
        self.assertEqual(self.session.state['phase'], 'ARMED')
        self.clock.value = 11
        self.docker.info['State'].update(Running=True, Status='running')
        self.session.poll(self.frame(), export_requested=True)
        self.assertEqual(self.session.state['phase'], 'EXPORTING')
        file = self.directory / 'guard.pulse'
        controller.pulse(file)
        lease = controller.Pulse(file, clock=self.clock)
        lease.age()
        controller.pulse(file)
        lease.age()
        return controller.GuardedExport(self.namespace, self.target, self.docker, lease)

    def collect(self, transport):
        return export.collect(transport, container_id=self.target.container_id,
                              plan_sha256=self.target.plan_sha256, metadata_sha256=SHA,
                              synthetic=True, clock=self.clock)

    def test_export_completion_requires_bound_receipt_exit_and_confirmed_removal(self):
        transport = self.exporting()
        def ack(*_):
            self.docker.info['State'].update(Running=False, Status='exited', ExitCode=0)
        with patch.object(transport, 'copy', side_effect=lambda path, _: path.write_bytes(archive())), \
                patch.object(export, 'acknowledge_export', side_effect=ack):
            directory, _ = self.collect(transport)
        self.clock.value = 12
        state = self.session.poll(self.frame(), export_requested=True, export_directory=directory)
        self.assertEqual(state['phase'], 'COMPLETE')
        self.assertTrue(state['stopConfirmed'])
        self.assertTrue(state['cleanupComplete'])
        self.assertIsNone(state['fault'])
        self.assertIsNone(self.docker.info)

    def test_hot_during_copy_stops_without_ack_and_fault_survives_restart(self):
        transport = self.exporting()
        def blocked_copy(path, _):
            self.clock.value = 12
            self.session.poll(self.frame(97))
            path.write_bytes(archive())
        with patch.object(transport, 'copy', side_effect=blocked_copy), patch.object(export, 'acknowledge_export') as ack:
            with self.assertRaises(ValueError):
                self.collect(transport)
            ack.assert_not_called()
        state = controller.read_json(self.namespace / 'state.json')
        self.assertEqual(state['phase'], 'FAULT')
        self.assertEqual(state['fault']['code'], 'CPU_HOT')
        self.assertTrue(state['stopConfirmed'])
        with self.assertRaisesRegex(ValueError, 'Latched fault'):
            controller.Session(self.namespace, self.directory, self.target, self.docker)

    def test_silent_sensor_or_lost_controller_trip_without_new_frame(self):
        self.exporting()
        self.clock.value = 14
        state = self.session.poll(controller_age=3)
        self.assertEqual(state['fault']['code'], 'CONTROLLER_LEASE_EXPIRED')
        self.assertTrue(state['cleanupComplete'])
        self.assertEqual(self.session.poll(cancelled=True)['fault']['code'], 'CONTROLLER_LEASE_EXPIRED')

    def test_sensor_gap_and_cancel_flow_through_stop_path(self):
        self.exporting()
        self.clock.value = 14
        self.assertEqual(self.session.poll()['fault']['code'], 'SENSOR_STALE')
        self.assertTrue(self.session.state['stopConfirmed'])

    def test_cancel_during_export_stops_worker(self):
        self.exporting()
        self.assertEqual(self.session.poll(cancelled=True)['fault']['code'], 'CANCELLED')
        self.assertTrue(self.session.state['cleanupComplete'])

    def test_failed_fault_journal_still_attempts_stop(self):
        self.exporting()
        with patch.object(self.session, '_save', side_effect=OSError('synthetic disk failure')):
            state = self.session.fail('CANCELLED')
        self.assertTrue(state['stopConfirmed'])
        self.assertEqual(state['journalError'], 'OSError')

    def test_fault_is_persisted_before_stop_and_policy_files_are_not_needed(self):
        self.exporting()
        original = self.docker.call
        observed = []
        def call(*args, **kwargs):
            if args[0] in ('stop', 'kill', 'rm'):
                observed.append(controller.read_json(self.namespace / 'state.json')['fault']['code'])
            return original(*args, **kwargs)
        with patch.object(self.docker, 'call', side_effect=call), \
                patch.object(policy, 'load_effective_controls', side_effect=OSError('approval file unavailable')):
            state = self.session.fail('CANCELLED')
        self.assertTrue(state['cleanupComplete'])
        self.assertTrue(observed)
        self.assertEqual(set(observed), {'CANCELLED'})

    def test_corrupt_or_active_journal_never_restarts(self):
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            controller.Session(self.namespace, self.directory, self.target, self.docker)
        (self.namespace / 'state.json').write_text('{')
        with self.assertRaises(ValueError):
            controller.Session(self.namespace, self.directory, self.target, self.docker)

    def test_changed_identity_is_never_stopped_or_removed(self):
        self.exporting()
        self.docker.info['Id'] = 'c' * 64
        state = self.session.fail('CANCELLED')
        self.assertFalse(state['stopConfirmed'])
        self.assertFalse(state['cleanupComplete'])
        self.assertFalse(any(args[0] in ('stop', 'kill', 'rm') for args in self.docker.calls))

    def test_fault_during_inspect_revokes_export_permission(self):
        transport = self.exporting()
        original = self.target.inspect
        def inspect(docker):
            info = original(docker)
            state = controller.read_json(self.namespace / 'state.json')
            state.update(phase='FAULT', fault={'code': 'SYNTHETIC_RACE'})
            guard.base.atomic(self.namespace / 'state.json', state)
            return info
        with patch.object(offline_target.Target, 'inspect', side_effect=inspect):
            with self.assertRaisesRegex(ValueError, 'changed during inspect'):
                transport.verify()

    def test_daemon_outage_is_latched_unconfirmed_not_success(self):
        self.exporting()
        self.docker.unavailable = True
        state = self.session.fail('CANCELLED')
        self.assertEqual(state['phase'], 'FAULT')
        self.assertEqual(state['stopFault'], 'STOP_UNCONFIRMED')
        self.assertFalse(state['cleanupComplete'])
        with self.assertRaises(ValueError):
            controller.Session(self.namespace, self.directory, self.target, self.docker)

    def test_export_requires_fresh_watchdog_progress(self):
        transport = self.exporting()
        self.clock.value = 14
        with self.assertRaisesRegex(ValueError, 'stale'):
            transport.verify()

    def test_wall_clock_gap_cannot_be_hidden_by_new_sensor_timestamp(self):
        self.exporting()
        self.clock.value = 12
        with patch.object(self.session, 'unix', return_value=10000):
            sample = self.frame()
            sample['recordedAtUnix'] = 10000
            state = self.session.poll(sample)
        self.assertEqual(state['fault']['code'], 'CLOCK_DISCONTINUITY')
        self.assertTrue(state['stopConfirmed'])

    def test_running_before_baseline_is_faulted(self):
        self.docker.info['State'].update(Running=True, Status='running')
        state = self.session.poll(self.frame())
        self.assertEqual(state['fault']['code'], 'WORKER_STARTED_BEFORE_BASELINE')
        self.assertTrue(state['stopConfirmed'])

    def test_real_frames_cannot_be_promoted_by_rehearsal(self):
        sample = self.frame()
        sample['synthetic'] = False
        self.assertEqual(self.session.poll(sample)['fault']['code'], 'SYNTHETIC_ONLY')

    def test_offline_proposal_matcher_never_enables_live_session(self):
        summary = build_preflight.offline_summary()
        frozen = offline_target.from_proposal(summary['directory'], summary['planSha256'], 'a' * 64)
        self.assertFalse(frozen.synthetic)
        self.assertEqual(json.loads(frozen.contract_json)['host']['Memory'], 4294967296)
        with self.assertRaisesRegex(ValueError, 'disabled'):
            controller.Session(self.namespace, self.directory, frozen, self.docker)

    def test_matcher_rejects_identity_resources_capabilities_and_extra_mounts(self):
        original = copy.deepcopy(self.docker.info)
        changes = [lambda i: i.update(Id='c' * 64),
                   lambda i: i['HostConfig'].update(Memory=134217728),
                   lambda i: i['HostConfig'].update(ReadonlyRootfs=False),
                   lambda i: i['HostConfig'].update(CapAdd=['SYS_ADMIN']),
                   lambda i: i['HostConfig'].update(DeviceRequests=[{'Count': -1}]),
                   lambda i: i['HostConfig']['Tmpfs'].update({'/extra': 'rw,size=1g'}),
                   lambda i: i['Mounts'][0].update(RW=True),
                   lambda i: i['Mounts'].append({'Type': 'volume', 'Destination': '/secret'})]
        for change in changes:
            self.docker.info = copy.deepcopy(original)
            change(self.docker.info)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.target.inspect(self.docker)
        self.docker.info = copy.deepcopy(original)
        self.assertIsNotNone(self.target.inspect(self.docker))


if __name__ == '__main__':
    unittest.main()
