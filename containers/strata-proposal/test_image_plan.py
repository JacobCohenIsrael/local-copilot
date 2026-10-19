import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import image_plan as images


class ImagePlanTests(unittest.TestCase):
    def inputs(self):
        return (json.loads(images.read_metadata(images.HERE / 'cuda-base.manifest.json')),
                json.loads(images.read_metadata(images.HERE / 'cuda-base.config.json')))

    def checked_modified(self, manifest, config):
        raw_config = json.dumps(config).encode()
        manifest['config']['digest'] = 'sha256:' + hashlib.sha256(raw_config).hexdigest()
        manifest['config']['size'] = len(raw_config)
        raw_manifest = json.dumps(manifest).encode()
        return images.metadata(raw_manifest, raw_config, expected_sha=hashlib.sha256(raw_manifest).hexdigest())

    def observation(self):
        return {'version': 1, 'mode': 'read-only-image-storage-probe', 'image': images.IMAGE,
                'probeExitCode': 0, 'cleanupComplete': True, 'stopConfirmed': True, 'recordedAtUnix': 1000,
                'sameHostVolume': True,
                'stageVolumeFreeBytes': 100 * images.GIB, 'dockerCandidateVolumeFreeBytes': 100 * images.GIB,
                'guestRootAvailableBytes': 100 * images.GIB, 'dockerBackingPathConfirmed': False}

    def test_pinned_metadata_has_exact_bytes_platform_and_ordered_diff_ids(self):
        identity = images.metadata()
        self.assertEqual(identity['platform'], 'linux/amd64')
        self.assertEqual(len(identity['layers']), 11)
        self.assertEqual(identity['layerBytes'], 3951075675)
        self.assertEqual(identity['lockedBlobBytes'], 3951095908)
        self.assertEqual(identity['configBytes'], 20233)
        self.assertTrue(all(len(row['expandedSha256']) == 64 for row in identity['layers']))

    def test_manifest_or_configuration_tampering_rejected(self):
        raw_manifest = images.read_metadata(images.HERE / 'cuda-base.manifest.json')
        raw_config = images.read_metadata(images.HERE / 'cuda-base.config.json')
        for manifest, config in ((raw_manifest + b' ', raw_config), (raw_manifest, raw_config + b' ')):
            with self.assertRaises(ValueError):
                images.metadata(manifest, config)

    def test_semantic_bounds_still_reject_even_newly_rehashed_inputs(self):
        baseline_manifest, baseline_config = self.inputs()
        variants = [lambda m, c: c.update(architecture='arm64'),
                    lambda m, c: c.update(os='windows'),
                    lambda m, c: c['rootfs']['diff_ids'].pop(),
                    lambda m, c: m['layers'][0].update(urls=['https://foreign.invalid/blob']),
                    lambda m, c: m['layers'][0].update(size=True),
                    lambda m, c: m['layers'][0].update(size=-1),
                    lambda m, c: m['layers'][0].update(mediaType='unapproved/uncompressed'),
                    lambda m, c: c['rootfs']['diff_ids'].__setitem__(0, 'sha256:not-a-hash')]
        for variant in variants:
            manifest, config = copy.deepcopy(baseline_manifest), copy.deepcopy(baseline_config)
            variant(manifest, config)
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.checked_modified(manifest, config)

    def test_total_download_ceiling_checked_without_fetching_payload(self):
        manifest, config = self.inputs()
        manifest['layers'][5]['size'] = 3 * images.GIB
        manifest['layers'][9]['size'] = 3 * images.GIB
        with self.assertRaisesRegex(ValueError, '5 GiB ceiling'):
            self.checked_modified(manifest, config)

    def test_text_checkout_line_endings_preserve_remote_hash(self):
        original = images.read_metadata(images.HERE / 'cuda-base.manifest.json')
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'metadata.json'
            file.write_bytes(original.replace(b'\n', b'\r\n'))
            self.assertEqual(hashlib.sha256(images.read_metadata(file)).hexdigest(), images.MANIFEST_SHA)

    def test_oversized_metadata_rejected_before_json_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'large.json'
            file.write_bytes(b' ' * (images.METADATA_LIMIT + 1))
            with self.assertRaisesRegex(ValueError, 'exceeds limit'):
                images.read_metadata(file)

    def test_headroom_accounts_for_archive_compressed_and_expanded_data(self):
        budget = images.storage_budget(images.metadata())
        self.assertEqual(budget['hostStageBytes'], 2 * 3951095908 + 16 * 1024**2)
        self.assertEqual(budget['sameHostVolumeAvailableRequiredBytes'], 52672254252)
        self.assertGreater(budget['guestAvailableRequiredBytes'], images.EXPANDED_LIMIT)
        self.assertFalse(budget['expandedSizeMeasured'])
        self.assertFalse(budget['daemonHardDiskQuotaEnforced'])

    def test_plenty_of_space_does_not_grant_download_import_or_build_authority(self):
        report = images.report(self.observation())
        self.assertTrue(report['capacity']['withinProposedBudgetAtProbe'])
        self.assertFalse(report['capacity']['dockerBackingPathConfirmed'])
        self.assertFalse(report['capacity']['capacityIsReservationOrApproval'])
        self.assertTrue(report['downloadImplementation']['liveApprovalBridgeConnected'])
        self.assertTrue(report['downloadImplementation']['independentDownloadProcessGuardConnected'])
        self.assertFalse(report['downloadImplementation']['expandedStreamVerification']['actualPinnedLayersVerified'])
        self.assertTrue(report['downloadImplementation']['processSupervision']['productionConnected'])
        self.assertTrue(report['downloadImplementation']['processSupervision']['supervisorDeathCovered'])
        self.assertEqual(report['downloadImplementation']['blobCount'], 12)
        for flag in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'):
            self.assertFalse(report[flag])

    def test_shortage_on_either_host_or_guest_blocks_headroom(self):
        budget = images.storage_budget(images.metadata())
        for key in ('stageVolumeFreeBytes', 'dockerCandidateVolumeFreeBytes', 'guestRootAvailableBytes'):
            observation = self.observation()
            observation[key] = 0
            self.assertFalse(images.capacity(observation, budget)['withinProposedBudgetAtProbe'])

    def test_shared_volume_needs_combined_budget(self):
        budget = images.storage_budget(images.metadata())
        observation = self.observation()
        observation['stageVolumeFreeBytes'] = budget['sameHostVolumeAvailableRequiredBytes'] - 1
        self.assertFalse(images.capacity(observation, budget)['withinProposedBudgetAtProbe'])
        observation.update(sameHostVolume=False,
                           stageVolumeFreeBytes=budget['separateStageVolumeRequiredBytes'],
                           dockerCandidateVolumeFreeBytes=budget['separateDockerVolumeRequiredBytes'])
        self.assertTrue(images.capacity(observation, budget)['withinProposedBudgetAtProbe'])

    def test_unknown_or_invalid_capacity_is_not_guessed(self):
        budget = images.storage_budget(images.metadata())
        for key, value in [('stageVolumeFreeBytes', None), ('guestRootAvailableBytes', True),
                           ('guestRootAvailableBytes', -1), ('sameHostVolume', None), ('cleanupComplete', False),
                           ('stopConfirmed', False), ('recordedAtUnix', float('nan'))]:
            observation = self.observation()
            observation[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                images.capacity(observation, budget)

    def test_observation_pointer_hash_and_scope_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            storage = root / 'storage'
            session = storage / ('a' * 32)
            session.mkdir(parents=True)
            file = session / 'result.json'
            raw = json.dumps(self.observation()).encode()
            file.write_bytes(raw)
            pointer = root / 'image-storage-observation.json'
            candidate = {'version': 1, 'status': 'observation-only-not-approval', 'sessionId': session.name,
                         'receiptSha256': hashlib.sha256(raw).hexdigest(),
                         'imageDownloadEnabled': False, 'imageImportEnabled': False}
            pointer.write_text(json.dumps(candidate))
            with patch.object(images, 'HERE', root), patch.object(images, 'STORAGE_ROOT', storage):
                self.assertEqual(images.selected_observation(), self.observation())
                file.write_bytes(raw + b' ')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    images.selected_observation()
                file.write_bytes(raw)
                candidate['imageDownloadEnabled'] = True
                pointer.write_text(json.dumps(candidate))
                with self.assertRaisesRegex(ValueError, 'disabled observation'):
                    images.selected_observation()


if __name__ == '__main__':
    unittest.main()
