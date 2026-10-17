"""Exercise only PowerShell's contract-description path; never query hardware."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import build_policy_review as review

POWERSHELL = shutil.which('powershell.exe')
READER = Path(__file__).with_name('cpu_reader.ps1')


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell required for the reader contract')
class ReaderContractTests(unittest.TestCase):
    def describe(self, *args):
        return subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-File',
            str(READER), '-Describe', *args], capture_output=True, text=True, timeout=10)

    def test_full_session_contract_covers_baseline_build_and_stop(self):
        process = self.describe('-Samples', '1920')
        self.assertEqual(process.returncode, 0, process.stderr)
        contract = json.loads(process.stdout)
        self.assertFalse(contract['sensorAccessed'])
        self.assertFalse(contract['workloadStarted'])
        self.assertFalse(contract['longRunValidated'])
        self.assertAlmostEqual(contract['fractionalCoverageExample'], 1.9)
        self.assertLessEqual(contract['maxSamples'], contract['frameBudget'])
        draft, _ = review.load_draft()
        # Last emitted sample is one interval before the final coverage boundary.
        coverage = min(contract['maxDurationSeconds'],
                       (contract['requestedSamples'] - 1) * contract['sampleIntervalSeconds'])
        self.assertIsNone(review.coverage_error({'readerRemainingSeconds': coverage},
                                               draft, baseline_pending=True))

    def test_short_default_probe_cannot_admit_a_build(self):
        process = self.describe()
        self.assertEqual(process.returncode, 0, process.stderr)
        contract = json.loads(process.stdout)
        self.assertEqual(contract['requestedSamples'], 3)
        draft, _ = review.load_draft()
        remaining = (contract['requestedSamples'] - 1) * contract['sampleIntervalSeconds']
        self.assertEqual(review.coverage_error({'readerRemainingSeconds': remaining}, draft),
                         'READER_COVERAGE_INSUFFICIENT')

    def test_out_of_budget_sample_count_rejected_before_hardware(self):
        process = self.describe('-Samples', '1921')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('ParameterArgumentValidationError', process.stderr)


if __name__ == '__main__':
    unittest.main()
