"""One bounded start handoff; no Docker/process/hardware access or retries."""
import math
import re

CONTRACT={'coordination':'skip-periodic-inspect-only-during-one-guard-granted-start',
    'dockerStartSeconds':1.5,'periodicInspectSeconds':1,'handoffSeconds':2.5,
    'handoffBudgetSource':'existing-controller-guard-lease',
    'modelDeadlineAnchor':'guard-grant-before-container-start',
    'telemetryAndLeasesContinue':True,'automaticRetry':False}


def finite(value):return type(value) in (int,float) and math.isfinite(value)


class Handoff:
    def __init__(self,container_id,review_sha):
        if not re.fullmatch('[0-9a-f]{64}',container_id) or not re.fullmatch('[0-9a-f]{64}',review_sha):
            raise ValueError('START_HANDOFF_IDENTITY')
        self.container_id,self.review_sha=container_id,review_sha
        self.granted_at=None;self.completed=False

    def grant(self,now):
        if self.granted_at is not None or not finite(now):raise ValueError('START_HANDOFF_ALREADY_GRANTED_OR_CLOCK')
        self.granted_at=now

    def pending(self,now,receipt):
        if self.granted_at is None or not finite(now) or now<self.granted_at:
            raise ValueError('START_HANDOFF_CLOCK_OR_GRANT')
        if self.completed:return False
        if now-self.granted_at>=CONTRACT['handoffSeconds']:
            raise TimeoutError('MODEL_START_HANDOFF_DEADLINE')
        if receipt is None:return True
        if (not isinstance(receipt,dict) or set(receipt)!={'version','status','containerId','reviewSha256','startCalls','commandSeconds'} or
                type(receipt['version']) is not int or receipt['version']!=1 or receipt['status']!='START_RETURNED' or
                receipt['containerId']!=self.container_id or receipt['reviewSha256']!=self.review_sha or
                type(receipt['startCalls']) is not int or receipt['startCalls']!=1 or
                not finite(receipt['commandSeconds']) or not 0<=receipt['commandSeconds']<=CONTRACT['dockerStartSeconds']):
            raise ValueError('MODEL_START_RECEIPT_INVALID')
        self.completed=True
        return False


def receipt(container_id,review_sha,seconds):
    value={'version':1,'status':'START_RETURNED','containerId':container_id,
           'reviewSha256':review_sha,'startCalls':1,'commandSeconds':seconds}
    check=Handoff(container_id,review_sha);check.grant(0);check.pending(0,value)
    return value
