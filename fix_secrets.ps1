# Secret Manager の全Secret値から改行コードを除去するスクリプト
#　なぜかコピペに含まれるため

Write-Host "=== Starting Secret cleanup process ==="

# === 1. GEMINI_API_KEY ===
Write-Host "=== Fixing gemini-api-key ==="
$DIRTY_GEMINI = gcloud secrets versions access latest --secret="gemini-api-key"
$CLEAN_GEMINI = $DIRTY_GEMINI -replace "`r",'' -replace "`n",''
$CLEAN_GEMINI = $CLEAN_GEMINI.Trim()
Write-Host "Length: $($CLEAN_GEMINI.Length) chars"
$CLEAN_GEMINI | Out-File -FilePath temp_gemini.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add gemini-api-key --data-file=temp_gemini.txt
Remove-Item temp_gemini.txt

# === 2. GEMINI_MODEL_NAME ===
Write-Host "=== Fixing gemini-model-name ==="
$DIRTY_MODEL = gcloud secrets versions access latest --secret="gemini-model-name"
$CLEAN_MODEL = $DIRTY_MODEL -replace "`r",'' -replace "`n",''
$CLEAN_MODEL = $CLEAN_MODEL.Trim()
Write-Host "Value: $CLEAN_MODEL"
$CLEAN_MODEL | Out-File -FilePath temp_model.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add gemini-model-name --data-file=temp_model.txt
Remove-Item temp_model.txt

# === 3. SLACK_BOT_TOKEN ===
Write-Host "=== Fixing slack-bot-token ==="
$DIRTY_SLACK = gcloud secrets versions access latest --secret="slack-bot-token"
$CLEAN_SLACK = $DIRTY_SLACK -replace "`r",'' -replace "`n",''
$CLEAN_SLACK = $CLEAN_SLACK.Trim()
Write-Host "Length: $($CLEAN_SLACK.Length) chars, Starts with: $($CLEAN_SLACK.Substring(0, 8))"
$CLEAN_SLACK | Out-File -FilePath temp_slack.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add slack-bot-token --data-file=temp_slack.txt
Remove-Item temp_slack.txt

# === 4. SLACK_SIGNING_SECRET ===
Write-Host "=== Fixing slack-signing-secret ==="
$DIRTY_SIGN = gcloud secrets versions access latest --secret="slack-signing-secret"
$CLEAN_SIGN = $DIRTY_SIGN -replace "`r",'' -replace "`n",''
$CLEAN_SIGN = $CLEAN_SIGN.Trim()
Write-Host "Length: $($CLEAN_SIGN.Length) chars"
$CLEAN_SIGN | Out-File -FilePath temp_sign.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add slack-signing-secret --data-file=temp_sign.txt
Remove-Item temp_sign.txt

# === 5. STORAGE_BACKEND ===
Write-Host "=== Fixing storage-backend ==="
$DIRTY_STORAGE = gcloud secrets versions access latest --secret="storage-backend"
$CLEAN_STORAGE = $DIRTY_STORAGE -replace "`r",'' -replace "`n",''
$CLEAN_STORAGE = $CLEAN_STORAGE.Trim()
Write-Host "Value: $CLEAN_STORAGE"
$CLEAN_STORAGE | Out-File -FilePath temp_storage.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add storage-backend --data-file=temp_storage.txt
Remove-Item temp_storage.txt

# === 6. LOG_LEVEL ===
Write-Host "=== Fixing log-level ==="
$DIRTY_LOG = gcloud secrets versions access latest --secret="log-level"
$CLEAN_LOG = $DIRTY_LOG -replace "`r",'' -replace "`n",''
$CLEAN_LOG = $CLEAN_LOG.Trim()
Write-Host "Value: $CLEAN_LOG"
$CLEAN_LOG | Out-File -FilePath temp_log.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add log-level --data-file=temp_log.txt
Remove-Item temp_log.txt

# === 7. SOCKET_MODE ===
Write-Host "=== Fixing socket-mode ==="
$DIRTY_SOCKET = gcloud secrets versions access latest --secret="socket-mode"
$CLEAN_SOCKET = $DIRTY_SOCKET -replace "`r",'' -replace "`n",''
$CLEAN_SOCKET = $CLEAN_SOCKET.Trim()
Write-Host "Value: $CLEAN_SOCKET"
$CLEAN_SOCKET | Out-File -FilePath temp_socket.txt -Encoding UTF8 -NoNewline
gcloud secrets versions add socket-mode --data-file=temp_socket.txt
Remove-Item temp_socket.txt

Write-Host "=== All secrets cleaned successfully! ==="
Write-Host ""
Write-Host "=== Verification - Checking gemini-api-key for CRLF ==="
gcloud secrets versions access latest --secret="gemini-api-key" | od -c
