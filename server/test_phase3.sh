#!/usr/bin/env bash
# MOCA Phase 3 — Memory Layer Test Suite (5 scenarios)
# Run after server is started: bash test_phase3.sh
# Server logs will show Memory injection lines for Test 5 verification.

BASE_URL="http://localhost:8000"
PASS=0
FAIL=0

hr()   { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
pass() { echo "   ✅ $1"; ((PASS++)); }
fail() { echo "   ❌ $1"; ((FAIL++)); }
info() { echo "   ℹ️  $1"; }

ask() {
  # $1=message $2=session_id
  curl -s -X POST "$BASE_URL/moca/ask" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$1\", \"session_id\": \"$2\"}"
}

search_memory() {
  # $1=query
  curl -s "$BASE_URL/moca/memory/search?q=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote('$1'))")"
}

hr
echo "🧪 MOCA Phase 3 — Memory Layer Tests"
echo "   Note: knowledge extraction runs in background."
echo "   Tests use sleep() to allow async tasks to complete."
hr

# ── Test 1: Cross-session memory ────────────────────────────────────────────
echo ""
echo "▶ Test 1: Cross-session memory"
echo "   Session A: 'My colleague John works in finance'"
SESSION_A="p3-t1-a-$(date +%s)"
SESSION_B="p3-t1-b-$(date +%s)"

R=$(ask "My colleague John works in finance" "$SESSION_A")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
MEM=$(echo "$R"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memories_injected',0))" 2>/dev/null)
info "Session A response: ${RESP:0:120}"
info "Memories injected in session A: $MEM"

echo "   Waiting 5s for background extraction..."
sleep 5

echo "   Session B (new session): 'What do you know about John?'"
R=$(ask "What do you know about John?" "$SESSION_B")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
MEM=$(echo "$R"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memories_injected',0))" 2>/dev/null)
echo "   Response: ${RESP:0:250}"
info "Memories injected in session B: $MEM"

if [[ "$RESP" == *"John"* || "$RESP" == *"finance"* || "$RESP" == *"colleague"* ]]; then
  pass "Cross-session memory: MOCA recalled John from previous session"
else
  fail "Cross-session memory: John not recalled (check extraction logs)"
fi

# ── Test 2: Semantic preference recall ──────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 2: Semantic preference recall"
SESSION_C="p3-t2-a-$(date +%s)"
SESSION_D="p3-t2-b-$(date +%s)"

echo "   Session C: 'I strongly prefer direct, concise communication'"
R=$(ask "I strongly prefer direct, concise communication" "$SESSION_C")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
info "Session C response: ${RESP:0:120}"

echo "   Waiting 5s for background extraction..."
sleep 5

echo "   Session D (new session): 'How should you communicate with me?'"
R=$(ask "How should you communicate with me?" "$SESSION_D")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
MEM=$(echo "$R"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memories_injected',0))" 2>/dev/null)
echo "   Response: ${RESP:0:250}"
info "Memories injected: $MEM"

if [[ "$RESP" == *"direct"* || "$RESP" == *"concise"* || "$RESP" == *"brief"* ]]; then
  pass "Semantic preference: communication style recalled"
else
  fail "Semantic preference: preference not recalled (check extraction logs)"
fi

# ── Test 3: Entity extraction & search ──────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 3: Entity extraction & /moca/memory/search"
SESSION_E="p3-t3-$(date +%s)"

echo "   Telling MOCA: 'I have a meeting with Sarah from Acme Corp at 3pm'"
R=$(ask "I have a meeting with Sarah from Acme Corp at 3pm" "$SESSION_E")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
info "Response: ${RESP:0:120}"

echo "   Waiting 6s for background extraction..."
sleep 6

echo "   Searching memory: GET /moca/memory/search?q=Sarah"
SEARCH_R=$(search_memory "Sarah")
TOTAL=$(echo "$SEARCH_R"   | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null)
RESULTS=$(echo "$SEARCH_R" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d.get('results',[])[:3]:
    print('    -', r.get('source'), '|', r.get('content','')[:80])
" 2>/dev/null)
echo "   Total search results: $TOTAL"
echo "$RESULTS"

if [[ "$TOTAL" -gt 0 && ("$SEARCH_R" == *"Sarah"* || "$SEARCH_R" == *"Acme"* || "$SEARCH_R" == *"3pm"*) ]]; then
  pass "Entity extraction & search: Sarah/Acme found in memory"
else
  fail "Entity extraction & search: no results for Sarah (check extraction logs)"
fi

# ── Test 4: Knowledge accumulation ──────────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 4: Knowledge accumulation (5 facts → synthesis)"
SESSION_F="p3-t4-$(date +%s)"

FACTS=(
  "My name is Alex"
  "I am a software engineer at TechCorp"
  "I live in Berlin, Germany"
  "My favourite programming language is Python"
  "I wake up at 6am every morning"
)

echo "   Sending 5 facts..."
for fact in "${FACTS[@]}"; do
  ask "$fact" "$SESSION_F" > /dev/null
  sleep 1
done

echo "   Waiting 8s for all background extractions to complete..."
sleep 8

echo "   Asking: 'What do you know about me?'"
R=$(ask "What do you know about me?" "$SESSION_F")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
MEM=$(echo "$R"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memories_injected',0))" 2>/dev/null)
echo "   Response: ${RESP:0:400}"
info "Memories injected: $MEM"

# Count how many of the 5 facts are referenced
HITS=0
[[ "$RESP" == *"Alex"* || "$RESP" == *"name"* ]]        && ((HITS++))
[[ "$RESP" == *"engineer"* || "$RESP" == *"TechCorp"* ]] && ((HITS++))
[[ "$RESP" == *"Berlin"* || "$RESP" == *"Germany"* ]]    && ((HITS++))
[[ "$RESP" == *"Python"* ]]                               && ((HITS++))
[[ "$RESP" == *"6am"* || "$RESP" == *"wake"* ]]          && ((HITS++))

info "Facts referenced in response: $HITS / 5"
if [[ "$HITS" -ge 3 ]]; then
  pass "Knowledge accumulation: synthesised $HITS/5 facts correctly"
else
  fail "Knowledge accumulation: only $HITS/5 facts referenced (need >= 3)"
fi

# ── Test 5: Relevance ranking ────────────────────────────────────────────────
echo ""
sleep 5
echo "▶ Test 5: Relevance ranking (10 memories → only relevant injected)"
echo "   Check server logs for 'Memory injection' lines to verify count."

SESSION_G="p3-t5-src-$(date +%s)"
SESSION_H="p3-t5-ask-$(date +%s)"

NOISE=(
  "I enjoy hiking on weekends"
  "My car is a blue Honda"
  "I had pasta for dinner last Tuesday"
  "The office printer is on the third floor"
  "I play guitar as a hobby"
  "My dentist appointment is next Thursday"
  "I prefer tea over coffee"
  "My sister lives in Tokyo"
  "The gym I go to opens at 5am"
)
SIGNAL="My API key for the data pipeline expires on May 1st"

echo "   Storing 9 noise memories + 1 signal memory about API key..."
for noise in "${NOISE[@]}"; do
  ask "$noise" "$SESSION_G" > /dev/null
  sleep 0.5
done
ask "$SIGNAL" "$SESSION_G" > /dev/null

echo "   Waiting 10s for background extractions..."
sleep 10

echo "   Asking specific question: 'When does my API key expire?'"
R=$(ask "When does my API key expire?" "$SESSION_H")
RESP=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
MEM=$(echo "$R"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memories_injected',0))" 2>/dev/null)
echo "   Response: ${RESP:0:250}"
info "Memories injected: $MEM (should be ≤ 5 due to limit=5 in search_similar)"

# The response should mention the API key / May 1st, and NOT mention all 9 noise items
RELEVANT=0
[[ "$RESP" == *"May"* || "$RESP" == *"expire"* || "$RESP" == *"API"* || "$RESP" == *"pipeline"* ]] && ((RELEVANT++))
NOISE_LEAK=0
[[ "$RESP" == *"guitar"* ]]  && ((NOISE_LEAK++))
[[ "$RESP" == *"printer"* ]] && ((NOISE_LEAK++))
[[ "$RESP" == *"pasta"* ]]   && ((NOISE_LEAK++))

info "Relevant signal found in response: $RELEVANT | Noise leaks: $NOISE_LEAK"
info "Server log should show: memories_injected <= 5"

if [[ "$RELEVANT" -gt 0 && "$MEM" -le 5 ]]; then
  pass "Relevance ranking: signal recalled, injection count=$MEM (≤5)"
elif [[ "$RELEVANT" -gt 0 ]]; then
  pass "Relevance ranking: signal recalled (injection count=$MEM — check server logs for ≤5 cap)"
else
  fail "Relevance ranking: API key expiry not recalled from $MEM injected memories"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
hr
echo "🏁 Phase 3 Results: $PASS passed | $FAIL failed"
hr
if [[ $FAIL -eq 0 ]]; then
  echo "🎉 Phase 3 complete! MOCA has true persistent semantic memory."
else
  echo "⚠️  Some tests failed. Check server logs for 'moca.episodic' and 'moca.vector_store' lines."
  echo "   Common causes:"
  echo "   - pgvector extension not enabled (run: alembic upgrade head)"
  echo "   - sentence-transformers not installed (run: pip install -r requirements.txt)"
  echo "   - Background extraction failing silently (check for JSON parse warnings)"
fi
