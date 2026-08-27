"""Smoke-Test: stellt sicher, dass das Paket importierbar ist und die Toolchain läuft."""

import hr_policy_assistant


def test_package_importable():
    assert hr_policy_assistant.__doc__
