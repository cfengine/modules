#!/bin/bash
# Create or tear down a test LUKS2 encrypted volume for inventory-fde testing.
#
# Usage:
#   sudo ./test-encrypted-volume.sh setup    # Create and mount test volume
#   sudo ./test-encrypted-volume.sh teardown # Unmount and remove test volume
#
# The test volume uses a loopback device with a hardcoded passphrase ("testpass")
# and mounts at /mnt/fde-test. Requires cryptsetup and root privileges.

set -euo pipefail

IMG="/tmp/fde-test.img"
LOOP="/dev/loop100"
NAME="fde-test"
MNT="/mnt/${NAME}"
PASS="testpass"

setup() {
    if [ -e "/dev/mapper/${NAME}" ]; then
        echo "Test volume already exists at /dev/mapper/${NAME}"
        exit 1
    fi

    echo "Creating 100MB disk image..."
    dd if=/dev/zero of="${IMG}" bs=1M count=100 status=progress

    echo "Setting up loop device ${LOOP}..."
    losetup "${LOOP}" "${IMG}"

    echo "Formatting as LUKS2..."
    echo -n "${PASS}" | cryptsetup luksFormat --type luks2 "${LOOP}" --key-file=-

    echo "Opening LUKS volume as ${NAME}..."
    echo -n "${PASS}" | cryptsetup open "${LOOP}" "${NAME}" --key-file=-

    echo "Creating ext4 filesystem..."
    mkfs.ext4 -q "/dev/mapper/${NAME}"

    echo "Mounting at ${MNT}..."
    mkdir -p "${MNT}"
    mount "/dev/mapper/${NAME}" "${MNT}"

    echo ""
    echo "Test volume ready. Verify with:"
    echo "  cf-agent -KIf ./inventory-fde.cf --show-evaluated-vars=inventory_fde"
    echo ""
    echo "Tear down with:"
    echo "  sudo $0 teardown"
}

teardown() {
    echo "Tearing down test volume..."

    if mountpoint -q "${MNT}" 2>/dev/null; then
        echo "Unmounting ${MNT}..."
        umount "${MNT}"
    fi

    if [ -e "/dev/mapper/${NAME}" ]; then
        echo "Closing LUKS volume ${NAME}..."
        cryptsetup close "${NAME}"
    fi

    if losetup "${LOOP}" &>/dev/null; then
        echo "Detaching loop device ${LOOP}..."
        losetup -d "${LOOP}"
    fi

    if [ -f "${IMG}" ]; then
        echo "Removing disk image ${IMG}..."
        rm -f "${IMG}"
    fi

    if [ -d "${MNT}" ]; then
        rmdir "${MNT}" 2>/dev/null || true
    fi

    # Clean up cached LUKS2 JSON metadata
    rm -f /var/cfengine/state/inventory_fde_luks2_*.json

    echo "Teardown complete."
}

case "${1:-}" in
    setup)
        setup
        ;;
    teardown)
        teardown
        ;;
    *)
        echo "Usage: sudo $0 {setup|teardown}"
        exit 1
        ;;
esac
