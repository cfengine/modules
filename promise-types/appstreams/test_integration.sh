#!/bin/bash
# Integration test for the appstreams promise type.
# Requires a bootstrapped CFEngine agent on Rocky Linux 8 or 9.
#
# Usage:
#   ./test_integration.sh
#
# The test policy (test_appstreams_coverage.cf) must be deployed to
# /var/cfengine/inputs/services/cfbs/ and the appstreams promise type
# must be registered in services/init.cf before running this script.

set -euo pipefail

PASS=0
FAIL=0
BUNDLE="test_appstreams_coverage"
ROLE="role_node_js_app_server_enabled"

pass() { echo "  PASS: $*"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL + 1)); }

run_agent() {
    local classes="$1"
    cf-agent -KI -b "$BUNDLE" -D "$ROLE,$classes" 2>&1 || true
}

get_history_id() {
    dnf history list 2>/dev/null | awk '/^[[:space:]]*[0-9]/ {print $1; exit}' | tr -d ' ' || true
}

# Assert a new DNF history transaction was created since before_id.
# If pkg is provided, verify the transaction mentions that package.
assert_history_entry() {
    local before_id="$1" desc="$2" pkg="${3:-}"
    local after_id
    after_id=$(get_history_id)
    if [ "$after_id" = "$before_id" ]; then
        fail "dnf history: no transaction recorded ($desc)"
        return
    fi
    pass "dnf history: transaction $after_id recorded ($desc)"
    if [ -n "$pkg" ]; then
        if dnf history info "$after_id" 2>/dev/null | grep -qi "$pkg"; then
            pass "dnf history: transaction $after_id mentions $pkg"
        else
            fail "dnf history: transaction $after_id does not mention $pkg"
            dnf history info "$after_id" 2>/dev/null \
                | grep -iE "Package|Install|Remove|Upgrade|Module" \
                | head -10 | sed 's/^/    /'
        fi
    fi
}

# Assert no new DNF history transaction was created since before_id.
assert_no_history_entry() {
    local before_id="$1" desc="$2"
    local after_id
    after_id=$(get_history_id)
    if [ "$after_id" = "$before_id" ]; then
        pass "dnf history: no transaction for idempotent run ($desc)"
    else
        fail "dnf history: unexpected transaction $after_id for idempotent run ($desc)"
    fi
}

# Assert the Comment field of a history transaction contains a pattern.
assert_history_comment() {
    local id="$1" pattern="$2"
    if dnf history info "$id" 2>/dev/null | grep -qP "^Comment\s*:.*$pattern"; then
        pass "dnf history comment contains: $pattern"
    else
        fail "dnf history comment missing: $pattern"
        dnf history info "$id" 2>/dev/null | grep "^Comment" | sed 's/^/    /'
    fi
}

assert_repaired() {
    local output="$1" pattern="$2"
    if echo "$output" | grep -q "info:.*$pattern"; then
        pass "$pattern"
    else
        fail "expected repair: $pattern"
        echo "$output" | grep -E "info:|error:|CRITICAL" | sed 's/^/    /'
    fi
}

assert_kept() {
    local output="$1"
    if echo "$output" | grep -qE "^\s*(info:.*Repaired|error:|CRITICAL)"; then
        fail "expected KEPT but got repairs or errors"
        echo "$output" | grep -E "info:|error:|CRITICAL" | sed 's/^/    /'
    else
        pass "idempotent (no repairs)"
    fi
}

assert_rpm_installed() {
    local pkg="$1"
    if rpm -q "$pkg" &>/dev/null; then
        pass "$pkg is installed"
    else
        fail "$pkg is not installed"
    fi
}

assert_rpm_absent() {
    local pkg="$1"
    if ! rpm -q "$pkg" &>/dev/null; then
        pass "$pkg is absent"
    else
        fail "$pkg should not be installed"
    fi
}

assert_module_stream() {
    local module="$1" stream="$2" marker="$3" desc="$4"
    if dnf module list "$module" 2>/dev/null | grep -qP "$stream\s.*\[$marker\]"; then
        pass "$desc"
    else
        fail "$desc"
        dnf module list "$module" 2>/dev/null | grep "$module" | sed 's/^/    /'
    fi
}

assert_module_default() {
    local module="$1"
    # Filter the Hint line (which contains [e], [x], [i] as legend text)
    local listing
    listing=$(dnf module list "$module" 2>/dev/null | grep -v "^Hint:")
    if echo "$listing" | grep -qP "$module\s" && \
       ! echo "$listing" | grep -qP "\[e\]|\[x\]|\[i\]"; then
        pass "$module is in default state (no markers)"
    else
        fail "$module should have no stream markers"
        echo "$listing" | grep "$module" | sed 's/^/    /'
    fi
}

echo "========================================"
echo " appstreams promise type integration test"
echo "========================================"
echo

# ------------------------------------------------------------------
echo "Setup: resetting module state to a known baseline..."
dnf module reset ruby -y &>/dev/null || true
dnf module reset postgresql -y &>/dev/null || true
dnf remove postgresql-server -y &>/dev/null || true
echo

# ------------------------------------------------------------------
echo "Phase 1: enabled"
out=$(run_agent phase_enabled)
assert_repaired "$out" "ruby.*enabled"
assert_module_stream ruby 3.3 e "ruby:3.3 is enabled"
echo "  idempotency check"
out=$(run_agent phase_enabled)
assert_kept "$out"
echo

# ------------------------------------------------------------------
echo "Phase 2: installed (explicit profile)"
hid=$(get_history_id)
out=$(run_agent phase_installed)
assert_repaired "$out" "postgresql.*installed"
assert_rpm_installed postgresql-server
assert_history_entry "$hid" "installed postgresql:15/server" "postgresql"
last_id=$(get_history_id)
assert_history_comment "$last_id" "test_appstreams_coverage_postgresql_15_server_installed"
assert_history_comment "$last_id" "Install postgresql 15 server profile"

echo "  idempotency check"
hid=$(get_history_id)
out=$(run_agent phase_installed)
assert_kept "$out"
assert_no_history_entry "$hid" "installed postgresql:15/server"
echo

# ------------------------------------------------------------------
echo "Phase 3: disabled"
out=$(run_agent phase_disabled)
assert_repaired "$out" "ruby.*disabled"
assert_module_stream ruby 3.3 x "ruby:3.3 is disabled"
echo "  idempotency check"
out=$(run_agent phase_disabled)
assert_kept "$out"
echo

# ------------------------------------------------------------------
echo "Phase 4: removed"
hid=$(get_history_id)
out=$(run_agent phase_removed)
assert_repaired "$out" "postgresql.*removed"
assert_rpm_absent postgresql-server
assert_history_entry "$hid" "removed postgresql:15" "postgresql"
last_id=$(get_history_id)
assert_history_comment "$last_id" "test_appstreams_coverage_postgresql_15_removed"

echo "  idempotency check"
hid=$(get_history_id)
out=$(run_agent phase_removed)
assert_kept "$out"
assert_no_history_entry "$hid" "removed postgresql:15"
echo

# ------------------------------------------------------------------
echo "Phase 5: reset"
out=$(run_agent phase_reset)
assert_repaired "$out" "ruby.*reset"
assert_module_default ruby
echo "  idempotency check"
out=$(run_agent phase_reset)
assert_kept "$out"
echo

# ------------------------------------------------------------------
echo "Phase 6: stream switch (nodejs 20 -> 22)"
# Ensure we start from stream 20 for a meaningful switch test.
# dnf module install won't downgrade RPMs, so explicitly remove and reinstall.
dnf module reset nodejs -y &>/dev/null || true
dnf remove nodejs npm -y &>/dev/null || true
dnf module install nodejs:20/common -y &>/dev/null || true

hid=$(get_history_id)
out=$(run_agent phase_stream_switch)
assert_repaired "$out" "nodejs.*installed"
node_ver=$(node --version 2>/dev/null || echo "not found")
if echo "$node_ver" | grep -q "^v22\."; then
    pass "node version is $node_ver (stream 22)"
else
    fail "expected v22.x, got $node_ver"
fi
assert_history_entry "$hid" "stream switch nodejs 20->22" "nodejs"
last_id=$(get_history_id)
assert_history_comment "$last_id" "test_appstreams_coverage_nodejs_22_stream_switch"

echo "  idempotency check"
hid=$(get_history_id)
out=$(run_agent phase_stream_switch)
assert_kept "$out"
assert_no_history_entry "$hid" "stream switch nodejs 20->22"
echo

# ------------------------------------------------------------------
echo "========================================"
echo " Results: $PASS passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ]
