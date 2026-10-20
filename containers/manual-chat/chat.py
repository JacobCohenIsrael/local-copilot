"""Separate manual-chat CLI. prepare/review/status are offline only."""
import argparse
import json
import sys

import plan


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['prepare', 'review', 'status', 'run', 'stop'])
    parser.add_argument('--watch', action='store_true', help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.watch:
        import manual_supervisor
        manual_supervisor.watch()
        return 0
    if not options.command:
        parser.error('command required')
    if options.command == 'prepare':
        result = plan.prepare()
    elif options.command == 'review':
        digest, packet = plan.review()
        result = dict(reviewSha256=digest, scope=packet['scope'], policy=packet['policy'],
                      limits=packet['limits'], modelLaunchEnabled=False, approvalExists=plan.APPROVAL.exists())
    else:
        import manual_supervisor
        result = getattr(manual_supervisor, options.command)()
    print(json.dumps(result, indent=2), flush=True)
    return 3 if options.command == 'run' and result['status'] != 'MANUAL_SESSION_STOPPED_CONFIRMED' else 0


def cli():
    try:
        return main()
    except ValueError as error:
        if str(error) != 'MANUAL_CHAT_NOT_APPROVED':
            raise
        print('Manual chat has not been approved yet. No Docker or model operation was started.\n'
              'Approve the reviewed manual session in this chat first; its approval must be\n'
              'recorded before this command can launch the model.', file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(cli())
