<#
.SYNOPSIS
    Envia uma simulação (pasta com Depth*.tif do RAS Mapper) para o site.

.EXAMPLE
    .\enviar_simulacao.ps1 -Pasta "C:\Users\joelv\Desktop\newfolde1" -Nome "Itaipu" -Descricao "C'est um test"

.NOTES
    Na primeira vez, defina o servidor e o token (ou passe -Servidor/-Token):
        $env:SIMULACOES_SERVIDOR = "http://localhost:8000"
        $env:SIMULACOES_TOKEN    = "<o mesmo SIMULACOES_UPLOAD_TOKEN do .env do servidor>"
    Funciona no Windows PowerShell 5.1 e no PowerShell 7 (usa o curl.exe que vem no Windows 10+).
#>
param(
    [Parameter(Mandatory = $true)] [string] $Pasta,
    [Parameter(Mandatory = $true)] [string] $Nome,
    [string] $Descricao = "",
    [string] $Servidor = $env:SIMULACOES_SERVIDOR,
    [string] $Token = $env:SIMULACOES_TOKEN
)

$ErrorActionPreference = "Stop"
# Lê a resposta do curl.exe (JSON em UTF-8) sem estragar os acentos.
[Console]::OutputEncoding = [Text.Encoding]::UTF8

if (-not $Servidor) { $Servidor = "http://localhost:8000" }
if (-not $Token) { throw "Token não informado. Use -Token ou defina `$env:SIMULACOES_TOKEN." }
if (-not (Test-Path -LiteralPath $Pasta -PathType Container)) { throw "Pasta não encontrada: $Pasta" }

$arquivos = Get-ChildItem -LiteralPath $Pasta -Filter "Depth*.tif" -File
if ($arquivos.Count -eq 0) { throw "Nenhum arquivo Depth*.tif em $Pasta" }

$tamanhoMB = [math]::Round(($arquivos | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "Compactando $($arquivos.Count) arquivo(s) ($tamanhoMB MB)..."

$zip = Join-Path ([IO.Path]::GetTempPath()) ("simulacao_" + [guid]::NewGuid().ToString("N") + ".zip")
try {
    Compress-Archive -LiteralPath $arquivos.FullName -DestinationPath $zip -CompressionLevel Optimal

    Write-Host "Enviando para $Servidor ... (o servidor processa antes de responder, pode demorar)"
    $url = $Servidor.TrimEnd("/") + "/flood/api/upload/"

    # --form-string: envia nome/descrição como texto literal (sem o curl
    # interpretar '@' ou '<' no início como "ler arquivo").
    $resposta = & curl.exe -sS --fail-with-body -X POST $url `
        -H "Authorization: Bearer $Token" `
        -F "arquivo=@$zip;type=application/zip" `
        --form-string "nome=$Nome" `
        --form-string "descricao=$Descricao"
    $codigo = $LASTEXITCODE

    $json = $null
    try { $json = ($resposta -join "`n") | ConvertFrom-Json } catch { }

    if ($json -and $json.log) { Write-Host $json.log }
    if ($codigo -ne 0 -or -not $json -or -not $json.ok) {
        $erro = if ($json -and $json.erro) { $json.erro } else { $resposta -join "`n" }
        throw "Falha no envio: $erro"
    }
    Write-Host "OK! Simulação disponível em: $($Servidor.TrimEnd('/'))$($json.url)" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
}
