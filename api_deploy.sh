#!/usr/bin/env bash
# api_deploy.sh -- deploy a single file to a GitHub repo via the REST API.
# Bypasses git fetch/push (broken on this network). Uses HTTPS API calls only.
# Works for any repo owned by JohanBenade (token reaches both inspections-pwa and schools-pwa).
#
# USAGE:
#   bash api_deploy.sh <repo> <local_file> <repo_path> <branch_name> "<commit_message>"
#
# EXAMPLES:
#   bash api_deploy.sh JohanBenade/inspections-pwa ~/Downloads/batches.py \
#        app/routes/batches.py fix/af017 "fix(af017): remove dead code"
#   bash api_deploy.sh JohanBenade/schools-pwa ~/Downloads/attendance.py \
#        app/routes/attendance.py fix/x "fix(x): something"
#
# It will: read main, create the branch, commit the file, open a PR, print the PR URL.
# It does NOT merge -- you merge in the browser so the invariants/CI gate runs.

set -euo pipefail

TOKEN_FILE="${HOME}/.gh_deploy_token"

if [ "$#" -ne 5 ]; then
  echo "ERROR: need 5 args."
  echo "Usage: bash api_deploy.sh <repo> <local_file> <repo_path> <branch_name> \"<commit_message>\""
  echo "  e.g. bash api_deploy.sh JohanBenade/schools-pwa ~/Downloads/x.py app/x.py fix/x \"fix: x\""
  exit 1
fi
REPO="$1"
LOCAL_FILE="$2"
REPO_PATH="$3"
BRANCH="$4"
MESSAGE="$5"
API="https://api.github.com/repos/${REPO}"

if [ ! -f "$TOKEN_FILE" ]; then
  echo "ERROR: token file not found at $TOKEN_FILE"; exit 1
fi
if [ ! -f "$LOCAL_FILE" ]; then
  echo "ERROR: local file not found: $LOCAL_FILE"; exit 1
fi
TOKEN="$(cat "$TOKEN_FILE")"
AUTH="Authorization: Bearer ${TOKEN}"

echo "== api_deploy =="
echo "  repo       : $REPO"
echo "  local file : $LOCAL_FILE"
echo "  repo path  : $REPO_PATH"
echo "  branch     : $BRANCH"
echo "  message    : $MESSAGE"
echo

# 1. main tip SHA
MAIN_SHA="$(curl -s -H "$AUTH" "${API}/git/refs/heads/main" | grep '"sha"' | head -1 | cut -d'"' -f4)"
if [ -z "$MAIN_SHA" ]; then echo "ERROR: could not read main SHA (auth/network)."; exit 1; fi
echo "[1/5] main tip: $MAIN_SHA"

# 2. existing blob SHA (update mode) or blank (create mode)
FILE_SHA="$(curl -s -H "$AUTH" "${API}/contents/${REPO_PATH}?ref=main" | grep '"sha"' | head -1 | cut -d'"' -f4 || true)"
if [ -n "$FILE_SHA" ]; then echo "[2/5] existing blob: $FILE_SHA (update mode)"; else echo "[2/5] no file at path (create mode)"; fi

# 3. create branch
CREATE_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"ref\":\"refs/heads/${BRANCH}\",\"sha\":\"${MAIN_SHA}\"}" "${API}/git/refs")"
if [ "$CREATE_CODE" = "201" ]; then echo "[3/5] branch created: $BRANCH"
elif [ "$CREATE_CODE" = "422" ]; then echo "ERROR: branch '$BRANCH' already exists (422). Pick a new name."; exit 1
else echo "ERROR: branch create failed (HTTP $CREATE_CODE)."; exit 1; fi

# 4. commit file via Contents API
CONTENT_B64="$(base64 < "$LOCAL_FILE" | tr -d '\n')"
PAYLOAD_FILE="$(mktemp)"
{
  printf '{'
  printf '"message":%s,' "$(printf '%s' "$MESSAGE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  printf '"branch":"%s",' "$BRANCH"
  printf '"content":"%s"' "$CONTENT_B64"
  [ -n "$FILE_SHA" ] && printf ',"sha":"%s"' "$FILE_SHA"
  printf '}'
} > "$PAYLOAD_FILE"
PUT_CODE="$(curl -s -o /tmp/api_deploy_put.json -w "%{http_code}" -X PUT -H "$AUTH" -H "Content-Type: application/json" \
  --data-binary "@${PAYLOAD_FILE}" "${API}/contents/${REPO_PATH}")"
rm -f "$PAYLOAD_FILE"
if [ "$PUT_CODE" = "200" ] || [ "$PUT_CODE" = "201" ]; then echo "[4/5] file committed (HTTP $PUT_CODE)"
else
  echo "ERROR: commit failed (HTTP $PUT_CODE):"; cat /tmp/api_deploy_put.json; echo
  echo "Cleaning up branch $BRANCH ..."; curl -s -o /dev/null -X DELETE -H "$AUTH" "${API}/git/refs/heads/${BRANCH}"; exit 1
fi

# 5. open PR
PR_PAYLOAD="$(mktemp)"
{
  printf '{'
  printf '"title":%s,' "$(printf '%s' "$MESSAGE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  printf '"head":"%s",' "$BRANCH"
  printf '"base":"main"'
  printf '}'
} > "$PR_PAYLOAD"
PR_URL="$(curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" --data-binary "@${PR_PAYLOAD}" "${API}/pulls" \
  | grep '"html_url"' | head -1 | cut -d'"' -f4)"
rm -f "$PR_PAYLOAD"
if [ -n "$PR_URL" ]; then
  echo "[5/5] PR opened:"; echo "      $PR_URL"; echo
  echo "NEXT: open that URL, wait for checks to go green, then Merge."
else
  echo "WARN: committed to $BRANCH but no PR URL. Open manually: https://github.com/${REPO}/pull/new/${BRANCH}"
fi
