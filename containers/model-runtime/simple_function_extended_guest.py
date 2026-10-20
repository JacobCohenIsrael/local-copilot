"""Fresh Fibonacci scope: 900-second request, 1200-second hard model lifetime."""
import simple_function_guest as contract

REQUEST_SECONDS=900
MODEL_SECONDS=1200
LEASE_BYTES=4096


def main():
    import container_test_base as base
    base.REQUEST_SECONDS=REQUEST_SECONDS
    base.MODEL_SECONDS=MODEL_SECONDS
    base.LEASE_BYTES=LEASE_BYTES
    base.MAX_RESPONSE=contract.RESPONSE_BYTES
    base.validate_response=contract.validate_response
    return base.main()


if __name__=='__main__':raise SystemExit(main())
