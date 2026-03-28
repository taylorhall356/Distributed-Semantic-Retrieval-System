Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Eq {
    param (
        [Parameter(Mandatory = $true)] $Actual,
        [Parameter(Mandatory = $true)] $Expected,
        [Parameter(Mandatory = $true)] [string] $Label
    )

    if ($Actual -ne $Expected) {
        throw "FAIL: $Label (expected=$Expected actual=$Actual)"
    }

    Write-Output "PASS: $Label"
}

function Write-TestFiles {
    @'
%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 181 >>
stream
BT
/F1 18 Tf
72 720 Td
(Cats are playful household pets.) Tj
0 -28 Td
(Dogs enjoy walks and fetch.) Tj
0 -28 Td
(Quantum mechanics studies particles.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000481 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
551
%%EOF
'@ | Set-Content -Encoding ascii test_integration.pdf

    "not a pdf" | Set-Content -Encoding ascii test_integration.txt
}

function Cleanup-TestFiles {
    Remove-Item -LiteralPath test_integration.pdf,test_integration.txt -ErrorAction SilentlyContinue
}

try {
    Write-TestFiles

    $testRunId = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $primaryUsername = "itest_user_$testRunId"
    $secondaryUsername = "itest_other_$testRunId"

    docker compose up --build -d | Out-Null
    Start-Sleep -Seconds 25

    $health = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8080/health
    Assert-Eq $health.status 'ok' 'health endpoint'

    $signupBody = "{""username"":""$primaryUsername"",""password"":""strongpass123""}"
    $signup = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/auth/signup -ContentType 'application/json' -Body $signupBody
    Assert-Eq $signup.username $primaryUsername 'signup returns username'

    try {
        Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/auth/signup -ContentType 'application/json' -Body $signupBody | Out-Null
        throw 'FAIL: duplicate signup should fail'
    } catch {
        Assert-Eq $_.Exception.Response.StatusCode.value__ 409 'duplicate signup rejected'
    }

    $login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/auth/login -ContentType 'application/json' -Body $signupBody
    Assert-Eq $login.token_type 'bearer' 'login token type'

    $token = $login.access_token
    $headers = @{ Authorization = "Bearer $token" }

    $me = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8080/me -Headers $headers
    Assert-Eq $me.username $primaryUsername 'me endpoint uses jwt'

    try {
        Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8080/me | Out-Null
        throw 'FAIL: /me without token should fail'
    } catch {
        Assert-Eq $_.Exception.Response.StatusCode.value__ 401 'me without token rejected'
    }

    $invalidUpload = curl.exe -s -o - -w "`n%{http_code}" -X POST http://127.0.0.1:8080/documents -H "Authorization: Bearer $token" -F "file=@test_integration.txt;type=text/plain"
    $invalidUploadLines = $invalidUpload -split "`n"
    Assert-Eq $invalidUploadLines[-1] '400' 'non-pdf upload rejected'

    $uploadJson = curl.exe -s -X POST http://127.0.0.1:8080/documents -H "Authorization: Bearer $token" -F "file=@test_integration.pdf;type=application/pdf"
    $upload = $uploadJson | ConvertFrom-Json
    Assert-Eq $upload.status 'ready' 'pdf upload processed to ready'
    $docId = $upload.id

    $list = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8080/documents -Headers $headers
    Assert-Eq $list.Count 1 'document list count after upload'
    Assert-Eq $list[0].id $docId 'document list returns uploaded doc'

    $search = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8080/search?q=playful%20pet' -Headers $headers
    Assert-Eq $search.Count 3 'search returns chunk matches'
    Assert-Eq $search[0].filename 'test_integration.pdf' 'search returns expected filename'

    $secondarySignupBody = "{""username"":""$secondaryUsername"",""password"":""strongpass123""}"
    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/auth/signup -ContentType 'application/json' -Body $secondarySignupBody | Out-Null
    $otherLogin = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/auth/login -ContentType 'application/json' -Body $secondarySignupBody
    $otherHeaders = @{ Authorization = "Bearer $($otherLogin.access_token)" }
    $otherSearch = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8080/search?q=playful%20pet' -Headers $otherHeaders
    Assert-Eq $otherSearch.Count 0 'search is user-scoped'

    $deleteCode = curl.exe -s -o NUL -w "%{http_code}" -X DELETE http://127.0.0.1:8080/documents/$docId -H "Authorization: Bearer $token"
    Assert-Eq $deleteCode '204' 'delete document success'

    $afterDelete = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8080/documents -Headers $headers
    Assert-Eq $afterDelete.Count 0 'document list empty after delete'

    $secondDelete = curl.exe -s -o - -w "`n%{http_code}" -X DELETE http://127.0.0.1:8080/documents/$docId -H "Authorization: Bearer $token"
    $secondDeleteLines = $secondDelete -split "`n"
    Assert-Eq $secondDeleteLines[-1] '404' 'second delete returns 404'

    $qdrantCheck = docker exec semantic-retrieval-api python -c "from qdrant_client import QdrantClient; client=QdrantClient(host='qdrant', port=6333); res=client.scroll(collection_name='document_chunks', scroll_filter={'must':[{'key':'document_id','match':{'value':$docId}}]}, limit=10, with_payload=True); print(len(res[0]))"
    Assert-Eq $qdrantCheck.Trim() '0' 'qdrant points removed on delete'

    Write-Output 'ALL TESTS PASSED'
} finally {
    Cleanup-TestFiles
    docker compose down | Out-Null
}
