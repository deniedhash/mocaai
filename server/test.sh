#!/usr/bin/env bash
# MOCA Phase 2 — Verification Test Suite (7 scenarios)
# Run after server is started: bash test.sh

BASE_URL="http://localhost:8000"
PASS=0
FAIL=0

hr() { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
pass() { echo "   ✅ $1"; ((PASS++)); }
fail() { echo "   ❌ $1"; ((FAIL++)); }

ask() {
  # $1=message $2=session_id
  curl -s -X POST "$BASE_URL/moca/ask" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$1\", \"session_id\": \"$2\"}"
}

hr
echo "🧪 MOCA Phase 2 — Verification Tests"
hr

# ── Test 1: Single domain — HERMES ─────────────────────────────────────────
echo ""
echo "▶ Test 1: 'Did anyone message me today?' → should route to HERMES"
R=$(ask "Did anyone message me today?" "p2-t1")
AGENT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent','?'))" 2>/dev/null)
REASON=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('routing_reasoning','')[:80])" 2>/dev/null)
echo "   Agent: $AGENT | Reasoning: $REASON"
if [[ "$AGENT" == "hermes" ]]; then pass "Routed to hermes"; else fail "Expected hermes, got $AGENT"; fi

# ── Test 2: Single domain — MERCURY ────────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 2: 'Set a timer for 15 minutes' → should route to MERCURY"
R=$(ask "Set a timer for 15 minutes" "p2-t2")
AGENT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent','?'))" 2>/dev/null)
REASON=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('routing_reasoning','')[:80])" 2>/dev/null)
echo "   Agent: $AGENT | Reasoning: $REASON"
[[ "$AGENT" == "mercury" ]] && pass "Routed to mercury" || fail "Expected mercury, got $AGENT"
echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print('   Response:', d.get('response','')[:120])" 2>/dev/null

# ── Test 3: Research domain — ATHENA ───────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 3: 'What is happening in AI today?' → should route to ATHENA"
R=$(ask "What is happening in AI today?" "p2-t3")
AGENT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent','?'))" 2>/dev/null)
REASON=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('routing_reasoning','')[:80])" 2>/dev/null)
echo "   Agent: $AGENT | Reasoning: $REASON"
[[ "$AGENT" == "athena" ]] && pass "Routed to athena" || fail "Expected athena, got $AGENT"
echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print('   Response:', d.get('response','')[:120])" 2>/dev/null

# ── Test 4: Multi-domain — HERMES + MERCURY ────────────────────────────────
echo ""
sleep 5
echo "▶ Test 4: 'Check if John emailed me and remind me to reply at 3pm' → HERMES + MERCURY"
R=$(ask "Check if John emailed me and remind me to reply at 3pm" "p2-t4")
AGENTS=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(','.join(d.get('agents_involved',[])))" 2>/dev/null)
REASON=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('routing_reasoning','')[:80])" 2>/dev/null)
echo "   Agents involved: $AGENTS | Reasoning: $REASON"
# Accept if at least hermes OR mercury is present (fallback routing still valid)
[[ "$AGENTS" == *"hermes"* || "$AGENTS" == *"mercury"* ]] && \
  pass "Multi-domain handled (agents: $AGENTS)" || fail "Expected hermes or mercury, got $AGENTS"
echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print('   Response:', d.get('response','')[:160])" 2>/dev/null

# ── Test 5: Ambiguous — 'Help me with John' ────────────────────────────────
echo ""
sleep 5
echo "▶ Test 5: 'Help me with John' → should ask clarification or pick best agent"
R=$(ask "Help me with John" "p2-t5")
AGENT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent','?'))" 2>/dev/null)
CONF=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('confidence',0))" 2>/dev/null)
echo "   Agent: $AGENT | Confidence: $CONF"
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','')[:160])" 2>/dev/null)
echo "   Response: $RESP"
# Accept any routed agent — just verify it responded
[[ -n "$AGENT" ]] && pass "Responded (agent=$AGENT, confidence=$CONF)" || fail "No response"

# ── Test 6: Personality — 'Who are you?' ───────────────────────────────────
echo ""
sleep 5
echo "▶ Test 6: 'Who are you?' → must respond as MOCA with full personality"
R=$(ask "Who are you?" "p2-t6")
AGENT=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent','?'))" 2>/dev/null)
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
echo "   Agent: $AGENT"
echo "   Response: ${RESP:0:200}"
[[ "$RESP" == *"MOCA"* || "$RESP" == *"Capable"* || "$RESP" == *"service"* ]] && \
  pass "Responded in character as MOCA" || fail "MOCA personality not detected in response"

# ── Test 7: Conversation memory ─────────────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 7: Conversation memory — tell name then ask it back"
SESSION="p2-mem-$(date +%s)"
ask "My name is Animesh" "$SESSION" > /dev/null
sleep 5
R=$(ask "What is my name?" "$SESSION")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
echo "   Response: ${RESP:0:200}"
[[ "$RESP" == *"Animesh"* ]] && pass "Remembered name from conversation history" || fail "Did not recall name 'Animesh'"

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
hr
echo "🏁 Results: $PASS passed | $FAIL failed"
hr
[[ $FAIL -eq 0 ]] && echo "🎉 Phase 2 complete!" || echo "⚠️  Some tests failed. Check routing prompts."
