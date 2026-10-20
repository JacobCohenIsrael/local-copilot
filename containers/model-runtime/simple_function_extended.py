"""Fresh Fibonacci attempt with longer finite deadlines; safety thresholds unchanged."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import simple_function as prior
import simple_function_extended_guest as guest

p=prior.p
REPO,HERE=prior.REPO,prior.HERE
ROOT=REPO/'.runtime/strata-fibonacci-extended-review'
LIVE=REPO/'.runtime/strata-fibonacci-extended-model'
OPERATION=REPO/'.runtime/strata-fibonacci-extended-operation'
SCOPE='one-fresh-fibonacci-900s-request-1200s-model-safety-unchanged'
FAILED_SHA='7d4942f8f036a09979bc014f956edc8528c1f1c43cf44e9f299b826c5953546d'
FAILED=prior.ROOT/FAILED_SHA
FAILED_MANIFEST='be1454e34a0f6145fff5e10f7f6af02140f77a13f48250205eda845f6261b093'
REPORT=REPO/'.runtime/strata-simple-function-report'
REPORT_MANIFEST='ad6d8a36ac01ed3138015079b7fbc6969e96ac45ecb417c04101c1d53406149c'
SCRIPTS={'api_wrapper.py':'api_wrapper.py','container_test.py':'simple_function_extended_guest.py',
         'container_test_base.py':'container_test_duration.py','simple_function_guest.py':'simple_function_guest.py'}
DURATION={'requestSeconds':900,'modelSeconds':1200,'outerSeconds':1310,
          'cpuReaderSamples':1500,'gpuSampleLimit':1536,'pulseBytes':4096,
          'startupSecondsUnchanged':180,'admissionSecondsUnchanged':90,
          'engineSilenceSecondsUnchanged':75,'stopSecondsUnchanged':5,
          'freshnessSecondsUnchanged':2.5,'leaseSecondsUnchanged':2.5,
          'automaticRetry':False}
_active=False


def timeout_proof(verify=False):
    if p.build.tools.sha(FAILED/'execution-preservation.json')!=FAILED_MANIFEST:
        raise ValueError('FIBONACCI_FAILURE_MANIFEST_CHANGED')
    manifest=p.read(FAILED/'execution-preservation.json',1048576)
    if p.build.tools.sha(FAILED/'execution-result.json')!=manifest['executionResultSha256']:
        raise ValueError('FIBONACCI_FAILURE_RESULT_CHANGED')
    result=p.read(FAILED/'execution-result.json',1048576)
    if (result['status']!='STRATA_SIMPLE_FUNCTION_FAULT_CONFIRMED_STOPPED' or
            result['reviewSha256']!=FAILED_SHA or result['totalConsumedModelAttempts']!=16 or
            result['operationApprovalConsumed'] is not True or result['modelAttemptClaimed'] is not True or
            result['independentShutdownConfirmed'] is not True or result['allObservedHostHelpersExited'] is not True or
            result['allFourModelHelpersRecorded'] is not True or result['previousEvidenceVerified'] is not True or
            result['apiResult']['errorType']!='TimeoutError' or result['apiResult']['requestsSubmitted']!=1 or
            result['modelState']['fault']['code']!='API_TEST_FAILED' or result['modelState']['stopConfirmed'] is not True or
            result['repositoryEdits'] is not False or result['patchApplied'] is not False):
        raise ValueError('FIBONACCI_FAILURE_COMPLETION_CHANGED')
    if result['independentModelState']['Running'] or result['independentModelState']['Pid']!=0:
        raise ValueError('FIBONACCI_FAILURE_STOP_CHANGED')
    if p.build.tools.sha(HERE/'simple-function-approval.json')!=manifest['reviewEvidence']['owner-approved-decision.json']['sha256']:
        raise ValueError('FIBONACCI_FAILURE_APPROVAL_CHANGED')
    if p.build.tools.sha(REPORT/'preservation.json')!=REPORT_MANIFEST:
        raise ValueError('FIBONACCI_REPORT_CHANGED')
    report=p.read(REPORT/'preservation.json')
    if p.build.tools.sha(REPORT/'notes.json')!=report['notesSha256'] or report['executionPreservationSha256']!=FAILED_MANIFEST:
        raise ValueError('FIBONACCI_REPORT_NOTES_CHANGED')
    if verify:
        records=[manifest[k] for k in ('operation','launcher','attempt','reader')]+manifest['capacityProbeCandidates']
        for record in records:
            directory=Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()}!=set(record['files']):
                raise ValueError('FIBONACCI_FAILURE_FILE_SET_CHANGED')
            for name,item in record['files'].items():
                path=directory/name;p.build.tools.plain(path)
                if path.stat().st_size!=item['bytes'] or p.build.tools.sha(path)!=item['sha256']:
                    raise ValueError('FIBONACCI_FAILURE_FILE_CHANGED')
        if {x.relative_to(FAILED).as_posix() for x in FAILED.rglob('*') if x.is_file()}!=set(manifest['reviewEvidence'])|{'execution-preservation.json'}:
            raise ValueError('FIBONACCI_FAILURE_REVIEW_SET_CHANGED')
        for name,item in manifest['reviewEvidence'].items():
            path=FAILED/name;p.build.tools.plain(path)
            if path.stat().st_size!=item['bytes'] or p.build.tools.sha(path)!=item['sha256']:
                raise ValueError('FIBONACCI_FAILURE_REVIEW_CHANGED')
    return {'reviewSha256':FAILED_SHA,'preservationSha256':FAILED_MANIFEST,
            'resultSha256':manifest['executionResultSha256'],'reportPreservationSha256':REPORT_MANIFEST,
            'previousApprovalReused':False,'previousAttemptReset':False}


def same_limits(packet):
    old=p.read(FAILED/'review.json',131072)
    if packet['policy']!={**old['policy'],'modelSeconds':1200,'outerSeconds':1310}:
        raise ValueError('ONLY_REVIEWED_LIFETIME_CHANGE_ALLOWED')
    if packet['requestTimingChange']!={**old['requestTimingChange'],'hardRequestDeadlineSeconds':900}:
        raise ValueError('ONLY_REVIEWED_REQUEST_DEADLINE_CHANGE_ALLOWED')
    for key in ('configuration','request','functionTask','fileAccessChange','startupTargetChange','startupStatusChange',
                'vmEnvelope','settings','modelFiles','sourceLimitation','sourceReviewSha256','runtimeBundle',
                'buildProof','sourceTree','sourcePlan','limitations','controls','modelLargeFileBinding','startupSourceAudit'):
        if packet[key]!=old[key]:raise ValueError('EXTENDED_FIBONACCI_OTHER_LIMIT_OR_TASK_CHANGED')
    if packet.get('durationChange')!=DURATION or 'hostRamReadiness' in packet:
        raise ValueError('EXTENDED_FIBONACCI_DURATION_CONTRACT_CHANGED')
    for key in ('host','environment','gpuRequests','image','imageId','alternateImageId','entrypoint','command'):
        if packet['contract'][key]!=old['contract'][key]:raise ValueError('EXTENDED_FIBONACCI_CONTAINER_CHANGED')
    api=prior.history.task.coding.first_api
    if (p.INPUT_SCRIPTS!=SCRIPTS or api.READER_SAMPLES!=1500 or api.GPU_SAMPLE_LIMIT!=1536 or api.PULSE_BYTES!=4096 or
            api.API_RESULT_BYTES!=262144 or api.API_RESULT_RECORD_BYTES!=262144 or
            api.validate_response is not prior.guest.validate_response or guest.REQUEST_SECONDS!=900 or
            guest.MODEL_SECONDS!=1200 or guest.LEASE_BYTES!=4096):
        raise ValueError('EXTENDED_FIBONACCI_MONITOR_COVERAGE_CHANGED')
    inputs=Path(packet['packageDirectory'])/'input'
    if set(packet['inputSha256'])!=set(SCRIPTS)|{'request.json','strata.json'} or {x.name for x in inputs.iterdir()}!=set(packet['inputSha256']):
        raise ValueError('EXTENDED_FIBONACCI_INPUT_SET_CHANGED')
    if p.read(inputs/'request.json')!=old['request'] or p.read(inputs/'strata.json')!=old['configuration']:
        raise ValueError('EXTENDED_FIBONACCI_BAKED_REQUEST_CHANGED')
    for name,source in SCRIPTS.items():
        expected=hashlib.sha256((HERE/source).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if packet['inputSha256'][name]!=expected or p.build.tools.sha(inputs/name)!=expected:
            raise ValueError('EXTENDED_FIBONACCI_GUEST_CHANGED')


def activate():
    global _active
    if _active:return
    prior.activate()
    previous,proofs,prepare_packet=p.previous,p.expected_proofs,p.prepare
    prior.ROOT,prior.LIVE,prior.OPERATION=ROOT,LIVE,OPERATION
    p.ROOT,p.LIVE,p.APPROVAL,p.SCOPE=ROOT,LIVE,HERE/'simple-function-extended-approval.json',SCOPE
    p.safety.POLICY={**p.safety.POLICY,'modelSeconds':1200,'outerSeconds':1310}
    p.REQUEST_TIMING_CHANGE={**p.REQUEST_TIMING_CHANGE,'hardRequestDeadlineSeconds':900}
    p.INPUT_SCRIPTS=dict(SCRIPTS)
    p.previous=lambda:{**previous(),'fibonacciTimeout':timeout_proof(True)}
    p.expected_proofs=lambda:{**proofs(),'fibonacciTimeout':timeout_proof()}
    p.prepare=lambda extra=None:prepare_packet({**(extra or {}),'durationChange':copy.deepcopy(DURATION)})
    p.same_limits=same_limits
    api=prior.history.task.coding.first_api
    api.READER_SAMPLES,api.GPU_SAMPLE_LIMIT,api.PULSE_BYTES=1500,1536,4096
    api.WATCH_ENTRYPOINT=Path(__file__).resolve()
    _active=True


def prepare():
    activate()
    return prior.prepare()


def summary():
    activate()
    return prior.summary()


def run():
    activate()
    return prior.run()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',choices=['prepare','review','run'])
    parser.add_argument('--watch',action='store_true');options=parser.parse_args()
    if not options.watch and options.command is None:parser.error('command required')
    activate()
    if options.watch:prior.history.task.coding.first_api.watch()
    else:
        result=prepare() if options.command=='prepare' else summary() if options.command=='review' else run()
        print(json.dumps(result,indent=2),flush=True)
        if options.command=='run' and result['status']!='STRATA_SIMPLE_FUNCTION_PASSED':raise SystemExit(3)
