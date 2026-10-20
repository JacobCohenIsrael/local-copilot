"""Scope-specific guest entry point; all other bounds stay in the shared runner."""
REQUEST_SECONDS = 150


def main():
    import container_test_base as base
    base.REQUEST_SECONDS = REQUEST_SECONDS
    return base.main()


if __name__ == '__main__': raise SystemExit(main())
