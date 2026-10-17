import json
import unittest
from unittest.mock import patch

import build_guard as guard


class Clock:
    value = 0

    def __call__(self):
        return self.value


class Docker:
    def __init__(self, clock, *, ignore_stop=False, unavailable=False, cleanup_failure=False):
        self.clock = clock
        self.info = {'Id': 'original', 'State': {'Running': True, 'ExitCode': 0}}
        self.calls = []
        self.ignore_stop, self.unavailable = ignore_stop, unavailable
        self.cleanup_failure = cleanup_failure
        self.costs = {}

    def call(self, *args, timeout):
        self.calls.append((args, timeout))
        cost = self.costs.get(args[0], .1)
        self.clock.value += min(cost, timeout)
        if cost > timeout:
            raise TimeoutError('Simulated unresponsive Docker call')
        if self.unavailable:
            raise RuntimeError('Docker unavailable')
        if args[:2] == ('container', 'inspect'):
            if self.info is None:
                raise guard.base.subprocess.CalledProcessError(1, args, stderr='No such container')
            return json.dumps([self.info])
        if args[0] == 'stop' and not self.ignore_stop:
            self.info['State']['Running'] = False
        if args[0] == 'kill':
            self.info['State'].update(Running=False, ExitCode=137)
        if args[0] == 'rm':
            if self.cleanup_failure:
                raise RuntimeError('Removal failed')
            self.info = None
        return ''


class StopDeadlineTests(unittest.TestCase):
    def run_stop(self, docker, clock, started=0):
        # Unit-test command deadlines independently of the matcher. Native Docker
        # rehearsals exercise the complete identity/isolation matcher separately.
        with patch.object(guard, 'inspect_target', side_effect=lambda client, _: client.inspect('owned')):
            return guard.stop_target(docker, {}, 'original', started=started, clock=clock)

    def test_graceful_exit_and_cleanup_are_confirmed_separately(self):
        clock = Clock()
        docker = Docker(clock)
        result = self.run_stop(docker, clock)
        self.assertTrue(result['stopConfirmed'])
        self.assertTrue(result['cleanupComplete'])
        self.assertLessEqual(result['stopSeconds'], 5)
        self.assertNotIn('kill', [args[0] for args, _ in docker.calls])

    def test_uncooperative_target_is_killed_and_confirmed(self):
        clock = Clock()
        docker = Docker(clock, ignore_stop=True)
        result = self.run_stop(docker, clock)
        self.assertEqual(result['exitCode'], 137)
        self.assertTrue(result['cleanupComplete'])
        self.assertLessEqual(result['stopSeconds'], 5)

    def test_hung_stop_call_reserves_time_for_kill_and_confirmation(self):
        clock = Clock()
        docker = Docker(clock)
        docker.costs['stop'] = 10
        result = self.run_stop(docker, clock)
        self.assertTrue(result['stopConfirmed'])
        self.assertEqual(result['exitCode'], 137)
        self.assertLessEqual(result['stopSeconds'], 5)

    def test_outage_is_unresolved_not_absence_or_cleanup(self):
        clock = Clock()
        docker = Docker(clock, unavailable=True)
        result = self.run_stop(docker, clock)
        self.assertEqual(result['stopFault'], 'STOP_UNCONFIRMED')
        self.assertFalse(result['cleanupComplete'])
        self.assertFalse(result['stopConfirmed'])
        self.assertEqual(len(docker.calls), 1)

    def test_consumed_budget_includes_time_before_cleanup_begins(self):
        clock = Clock()
        clock.value = 4.9
        docker = Docker(clock)
        result = self.run_stop(docker, clock)
        self.assertFalse(result['stopConfirmed'])
        self.assertFalse(result['cleanupComplete'])
        self.assertLessEqual(clock.value, 5)
        self.assertTrue(all(timeout <= .11 for _, timeout in docker.calls))

    def test_replaced_container_is_never_stopped_or_removed(self):
        clock = Clock()
        docker = Docker(clock)
        docker.info['Id'] = 'replacement'
        result = self.run_stop(docker, clock)
        self.assertEqual(result['stopFault'], 'STOP_UNCONFIRMED')
        self.assertEqual([args[0] for args, _ in docker.calls], ['container'])

    def test_failed_removal_does_not_erase_confirmed_exit(self):
        clock = Clock()
        docker = Docker(clock, cleanup_failure=True)
        result = self.run_stop(docker, clock)
        self.assertTrue(result['stopConfirmed'])
        self.assertFalse(result['cleanupComplete'])
        self.assertIn('cleanupError', result)


if __name__ == '__main__':
    unittest.main()
