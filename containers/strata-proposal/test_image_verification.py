import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import image_verification as verify
import verification_admission as admission
import verify_image_stage as fixture


def tiny(directory):
    packet, configuration, packed = fixture.fixture()
    packet.update(operation='verify-retained-cache-only', inputBytes=len(configuration) + len(packed),
                  writeNamespaceBytes=4 * 1024**2)
    cache = directory / 'retained-cache'
    cache.mkdir()
    (cache / packet['image']['configDigest'][7:]).write_bytes(configuration)
    (cache / packet['image']['layers'][0]['digest'][7:]).write_bytes(packed)
    return packet, cache


class VerificationKernelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.packet, self.cache = tiny(self.root)
        verify.stage.controller.pulse(self.root / 'controller.pulse')

    def run_pipeline(self):
        with patch.object(verify.download, 'RegistrySource', side_effect=AssertionError('Network forbidden')):
            return verify.pipeline(self.root, self.packet, self.cache, synthetic=True)

    def test_retained_bytes_verified_without_network_copy_or_mutation(self):
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.cache.iterdir()}
        result = self.run_pipeline()
        self.assertEqual(result['networkRequests'], 0)
        self.assertEqual(result['streams']['status'], 'STREAMS_VERIFIED_NOT_IMPORTED')
        self.assertFalse(result['streams']['extracted'])
        self.assertEqual(result['verifiedInputBytes'], self.packet['inputBytes'])
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.cache.iterdir()})

    def test_same_size_corrupt_config_never_succeeds(self):
        (self.cache / self.packet['image']['configDigest'][7:]).write_bytes(b'xx')
        with self.assertRaisesRegex(ValueError, 'CACHE_CHANGED'):
            self.run_pipeline()
        self.assertFalse((self.root / 'worker-result.json').exists())

    def test_missing_extra_or_linked_cache_rejected_without_download(self):
        target = self.cache / self.packet['image']['configDigest'][7:]
        target.unlink()
        with self.assertRaisesRegex(ValueError, 'CACHE_CHANGED'):
            self.run_pipeline()
        target.write_bytes(b'{}')
        (self.cache / 'extra').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'CACHE_CHANGED'):
            self.run_pipeline()

    def test_bad_diff_id_and_corrupt_stream_are_not_success(self):
        self.packet['image']['layers'][0]['expandedSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'DIFF_ID_MISMATCH'):
            self.run_pipeline()
        self.assertFalse((self.root / 'worker-result.json').exists())

    def test_cancel_and_lost_controller_block_before_cache_bodies(self):
        (self.root / 'cancel.request').touch()
        with patch.object(verify, 'cache_identity') as identity:
            with self.assertRaisesRegex(ValueError, 'GUARD_PERMISSION_LOST'):
                self.run_pipeline()
            identity.assert_not_called()

    def test_cache_metadata_change_after_verified_read_is_rejected(self):
        original = verify.stage.expand._verify
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            target = self.cache / self.packet['image']['configDigest'][7:]
            target.write_bytes(b'{}')
            return result
        with patch.object(verify.stage.expand, '_verify', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'CACHE_CHANGED'):
                self.run_pipeline()

    def test_result_scope_counts_and_enable_flags_cannot_be_forged(self):
        result = self.run_pipeline()
        for key, value in [('configVerified', False), ('verifiedInputBytes', 1), ('networkRequests', 1),
                           ('inputCacheChanged', True), ('imageDownloadEnabled', True), ('imageImportEnabled', True),
                           ('buildEnabled', True), ('modelLaunchEnabled', True), ('scope', 'other')]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'VERIFICATION_RESULT_INVALID'):
                verify.validate_result({**result, key: value}, self.packet, True)


class VerificationAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for key, value in [('ROOT', self.root/'review'), ('LIVE', self.root/'live'), ('APPROVAL', self.root/'approval.json')]:
            scope = patch.object(admission, key, value)
            scope.start()
            self.addCleanup(scope.stop)

    def decision(self, sha, packet):
        return {'version':1,'status':'owner-approved-one-cache-verification','scope':admission.SCOPE,
                'reviewSha256':sha,'recoveryOfFailedSession':packet['recoveryOf']['verificationSessionId'],
                'preservationSha256':admission.PRESERVATION_SHA,'sourceEvidenceSha256':packet['sourceEvidenceSha256'],
                'verificationPreservationSha256':admission.VERIFICATION_PRESERVATION_SHA,
                'acceptImageThermalPolicySha256':admission.build.sha(packet['thermalPolicy']),
                'acceptSourceLimitation':admission.image.LIMITATION,'acceptUnknownThrottleForThisScope':True,
                'maximumAttempts':1,'verificationEnabled':True,'synthetic':False,'ownerMessage':'Synthetic decision only',
                'imageDownloadEnabled':False,'imageImportEnabled':False,'buildEnabled':False,'modelLaunchEnabled':False}

    def test_missing_approval_refuses_before_any_work_or_new_claim(self):
        with patch.object(verify.stage.cpu_feed, 'Feed') as feed, patch.object(verify.stage.windows_job, 'Process') as process, \
                patch.object(verify.stage.probe_image_storage, 'probe') as probe, patch.object(verify, 'pipeline') as pipeline:
            for action in (verify.run, verify.child):
                with self.assertRaisesRegex(ValueError, 'IMAGE_VERIFICATION_NOT_APPROVED'):
                    action()
            for call in (feed, process, probe, pipeline):
                call.assert_not_called()
        self.assertFalse(admission.LIVE.exists())

    def test_preparation_checks_evidence_without_reading_real_blob_bodies(self):
        original = Path.open
        cache = admission.PREVIOUS / 'data/cache'
        def opened(path, *args, **kwargs):
            if path.parent == cache:
                raise AssertionError('Preparation must not read blob bytes')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', opened):
            directory, packet = admission.prepare()
            self.assertFalse(packet['preparationReadsCacheBodies'])
            self.assertEqual(packet['inputBytes'], 3951095908)
            self.assertEqual(packet['recoveryOf']['blobCount'], 12)
            self.assertFalse(admission.summary()['approved'])
            self.assertEqual(admission.review()[0], directory.name)

    def test_old_download_approval_cannot_authorize_verification(self):
        admission.prepare()
        admission.APPROVAL.write_bytes(admission.image.APPROVAL.read_bytes())
        with self.assertRaisesRegex(ValueError, 'SCOPE_OR_HASH_INVALID'):
            admission.authorize()

    def test_scope_and_preservation_and_download_disable_are_mandatory(self):
        directory, packet = admission.prepare()
        decision = self.decision(directory.name, packet)
        for key,value in [('version',True),('scope','other'),('reviewSha256','0'*64),
                          ('recoveryOfFailedSession','other'),('preservationSha256','0'*64),
                          ('verificationPreservationSha256','0'*64),
                          ('sourceEvidenceSha256','0'*64),('acceptImageThermalPolicySha256','0'*64),
                          ('acceptSourceLimitation','other'),('acceptUnknownThrottleForThisScope',False),
                          ('maximumAttempts',2),('maximumAttempts',True),('verificationEnabled',False),
                          ('synthetic',True),('ownerMessage',''),('imageDownloadEnabled',True),
                          ('imageImportEnabled',True),('buildEnabled',True),('modelLaunchEnabled',True)]:
            admission.APPROVAL.write_text(json.dumps({**decision,key:value}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'SCOPE_OR_HASH_INVALID'):
                admission.authorize()
        admission.APPROVAL.write_text(json.dumps(decision))
        permit=admission.authorize()
        self.assertEqual(permit.live_namespace,admission.LIVE)

    def test_consumed_attempt_refuses_before_fresh_reader_or_probe(self):
        directory,packet=admission.prepare()
        permit=admission.Permit(directory.name,admission.build.encoded(packet).decode(),'test')
        admission.LIVE.mkdir()
        (admission.LIVE/'attempt.json').write_text('{}')
        with patch.object(admission,'authorize',return_value=permit),patch.object(verify.stage.probe_image_storage,'probe') as probe:
            with self.assertRaisesRegex(ValueError,'ATTEMPT_ALREADY_CONSUMED'):
                verify.run()
            probe.assert_not_called()

    def test_helper_or_preserved_metadata_change_denies_review(self):
        admission.prepare()
        with patch.object(admission.build,'helpers',return_value={'changed':'helper'}):
            with self.assertRaisesRegex(ValueError,'stale'):
                admission.review()
        with patch.object(admission,'metadata_tree',return_value={}):
            with self.assertRaisesRegex(ValueError,'metadata changed'):
                admission.review()

    def test_spent_verification_receipt_cannot_authorize_new_namespace(self):
        admission.prepare()
        admission.APPROVAL.write_bytes(admission.PREVIOUS_VERIFICATION_APPROVAL.read_bytes())
        with patch.object(verify.stage.cpu_feed,'Feed') as feed, patch.object(verify.stage.probe_image_storage,'probe') as probe:
            with self.assertRaisesRegex(ValueError,'SCOPE_OR_HASH_INVALID'):
                verify.run()
            feed.assert_not_called()
            probe.assert_not_called()
        self.assertFalse(admission.LIVE.exists())

    def test_latest_fault_metadata_cannot_change_while_older_attempts_match(self):
        original=admission.metadata_tree
        def changed(directory,**kwargs):
            if directory==admission.PREVIOUS_VERIFICATION:
                return {}
            return original(directory,**kwargs)
        with patch.object(admission,'metadata_tree',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'Third attempt or reader'):
                admission.binding()

    def test_latest_code_preservation_record_is_hash_bound(self):
        original=admission.tools.sha
        def changed(path):
            if path==admission.ARCHIVE/'verification-code-preservation.json':
                return '0'*64
            return original(path)
        with patch.object(admission.tools,'sha',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'Third attempt preservation'):
                admission.binding()


if __name__ == '__main__':
    unittest.main()
