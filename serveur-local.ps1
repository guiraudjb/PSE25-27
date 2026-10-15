<#
Serveur web local de la page de révision (autohébergement, Windows PowerShell 5.1 ou PowerShell 7).

Lancé par lancer-site-local.bat (double-clic). Sert le dossier PARENT du dépôt sur http://localhost:<port>/
et ouvre le navigateur sur http://localhost:<port>/<dépôt>/ : la page, son moteur (sw.js, catalogue.json)
et les données du jeu (batocera/<dépôt>/data/, tts_assets/) sont lus sur le disque, sans Internet.
Servir le parent permet aux liens ../<autre dépôt>/ (page commune PSE25-27, dépôts associés) de
fonctionner quand les dépôts sont clonés côte à côte dans un même dossier.

Une page ouverte en file:// ne fonctionne pas (fetch des JSON/CSV et service worker refusés) :
d'où ce petit serveur, sans installation ni droits d'administrateur (écoute sur localhost uniquement).

Paramètres : -Port 8080 (premier port essayé, les suivants si occupé), -SansNavigateur.
Le moteur se modifie dans PSE25-27/ de l'espace de la refonte puis scripts/sync-web.py, jamais ici.
#>
param(
    [int]$Port = 8080,
    [switch]$SansNavigateur
)

$ErrorActionPreference = 'Stop'

$depotDir = (Resolve-Path -LiteralPath $PSScriptRoot).ProviderPath.TrimEnd('\', '/')
$nomDepot = Split-Path -Leaf $depotDir
$racine = Split-Path -Parent $depotDir
if (-not $racine) {
    # dépôt à la racine d'un lecteur : on sert le dépôt lui-même
    $racine = $depotDir
    $prefixe = ''
} else {
    $racine = $racine.TrimEnd('\', '/')
    $prefixe = [Uri]::EscapeDataString($nomDepot) + '/'
}

$types = @{
    '.html' = 'text/html; charset=utf-8'; '.htm' = 'text/html; charset=utf-8'
    '.js' = 'application/javascript; charset=utf-8'; '.mjs' = 'application/javascript; charset=utf-8'
    '.css' = 'text/css; charset=utf-8'; '.json' = 'application/json; charset=utf-8'
    '.webmanifest' = 'application/manifest+json; charset=utf-8'
    '.txt' = 'text/plain; charset=utf-8'; '.csv' = 'text/csv; charset=utf-8'; '.md' = 'text/markdown; charset=utf-8'
    '.png' = 'image/png'; '.jpg' = 'image/jpeg'; '.jpeg' = 'image/jpeg'; '.gif' = 'image/gif'
    '.webp' = 'image/webp'; '.svg' = 'image/svg+xml'; '.ico' = 'image/x-icon'
    '.mp3' = 'audio/mpeg'; '.m4a' = 'audio/mp4'; '.wav' = 'audio/wav'; '.ogg' = 'audio/ogg'
    '.mp4' = 'video/mp4'; '.webm' = 'video/webm'; '.pdf' = 'application/pdf'
    '.woff' = 'font/woff'; '.woff2' = 'font/woff2'; '.ttf' = 'font/ttf'
}

# Traitement des requêtes, exécuté en parallèle par plusieurs runspaces : un lecteur audio qui garde
# sa connexion ouverte (lecture progressive d'un mp3) ne bloque pas le reste de la page.
$travailleur = {
    param($listener, $racine, $prefixe, $types)
    $sep = [IO.Path]::DirectorySeparatorChar

    function Rediriger($res, $vers) {
        $res.StatusCode = 302
        $res.RedirectLocation = $vers
    }

    while ($listener.IsListening) {
        try { $ctx = $listener.GetContext() } catch { break }
        $req = $ctx.Request
        $res = $ctx.Response
        try {
            if ($req.HttpMethod -ne 'GET' -and $req.HttpMethod -ne 'HEAD') {
                $res.StatusCode = 405
                continue
            }
            $brut = $req.Url.AbsolutePath
            if ($brut -eq '/' -and $prefixe) { Rediriger $res ('/' + $prefixe); continue }

            $relatif = [Uri]::UnescapeDataString($brut).TrimStart('/').Replace('/', $sep)
            $plein = [IO.Path]::GetFullPath([IO.Path]::Combine($racine, $relatif))
            if ($plein -ne $racine -and -not $plein.StartsWith($racine + $sep, [StringComparison]::OrdinalIgnoreCase)) {
                $res.StatusCode = 403
                continue
            }
            if ([IO.Directory]::Exists($plein)) {
                if (-not $brut.EndsWith('/')) { Rediriger $res ($brut + '/'); continue }
                $plein = [IO.Path]::Combine($plein, 'index.html')
            }
            if (-not [IO.File]::Exists($plein)) {
                $res.StatusCode = 404
                continue
            }

            $ext = [IO.Path]::GetExtension($plein).ToLowerInvariant()
            $type = $types[$ext]
            if (-not $type) { $type = 'application/octet-stream' }
            $res.ContentType = $type
            $res.AddHeader('Accept-Ranges', 'bytes')
            $res.AddHeader('Cache-Control', 'no-cache')

            $flux = [IO.File]::Open($plein, 'Open', 'Read', 'ReadWrite')
            try {
                $taille = $flux.Length
                $debut = [long]0
                $fin = $taille - 1
                # requêtes partielles (Range) : nécessaires pour se déplacer dans un podcast
                $plage = $req.Headers['Range']
                if ($plage -and $plage -match '^bytes=(\d*)-(\d*)$') {
                    if ($Matches[1] -ne '') {
                        $debut = [long]$Matches[1]
                        if ($Matches[2] -ne '') { $fin = [Math]::Min([long]$Matches[2], $taille - 1) }
                    } elseif ($Matches[2] -ne '') {
                        $debut = [Math]::Max([long]0, $taille - [long]$Matches[2])
                    }
                    if ($debut -ge $taille -or $debut -gt $fin) {
                        $res.StatusCode = 416
                        $res.AddHeader('Content-Range', "bytes */$taille")
                        continue
                    }
                    $res.StatusCode = 206
                    $res.AddHeader('Content-Range', "bytes $debut-$fin/$taille")
                }
                $reste = $fin - $debut + 1
                if ($taille -eq 0) { $reste = 0 }
                $res.ContentLength64 = $reste
                if ($req.HttpMethod -eq 'GET' -and $reste -gt 0) {
                    [void]$flux.Seek($debut, 'Begin')
                    $tampon = New-Object byte[] 65536
                    $sortie = $res.OutputStream
                    while ($reste -gt 0) {
                        $n = $flux.Read($tampon, 0, [int][Math]::Min([long]$tampon.Length, $reste))
                        if ($n -le 0) { break }
                        $sortie.Write($tampon, 0, $n)
                        $reste -= $n
                    }
                }
            } finally {
                $flux.Dispose()
            }
        } catch {
            # client parti en cours de transfert (changement de piste audio…) ou erreur de lecture
            try { $res.StatusCode = 500 } catch { }
        } finally {
            try { $res.Close() } catch { }
        }
    }
}

# Premier port libre à partir de $Port (plusieurs dépôts peuvent tourner en même temps)
$listener = $null
foreach ($p in $Port..($Port + 30)) {
    $essai = New-Object System.Net.HttpListener
    $essai.Prefixes.Add("http://localhost:$p/")
    try {
        $essai.Start()
        $listener = $essai
        $Port = $p
        break
    } catch {
        $essai.Close()
    }
}
if (-not $listener) {
    Write-Host "Aucun port libre entre $Port et $($Port + 30)." -ForegroundColor Red
    exit 1
}

$nbTravailleurs = 8
$pool = [RunspaceFactory]::CreateRunspacePool(1, $nbTravailleurs)
$pool.Open()
$taches = @()
for ($i = 0; $i -lt $nbTravailleurs; $i++) {
    $ps = [PowerShell]::Create()
    $ps.RunspacePool = $pool
    [void]$ps.AddScript($travailleur).AddArgument($listener).AddArgument($racine).AddArgument($prefixe).AddArgument($types)
    $taches += [pscustomobject]@{ PS = $ps; Handle = $ps.BeginInvoke() }
}

$url = "http://localhost:$Port/$prefixe"
$Host.UI.RawUI.WindowTitle = "$nomDepot - $url"
Write-Host ''
Write-Host "  Page de révision « $nomDepot » servie en local" -ForegroundColor Green
Write-Host "  Adresse  : $url"
Write-Host "  Dossier  : $racine"
Write-Host ''
Write-Host '  Laisser cette fenêtre ouverte pendant la révision.'
Write-Host '  Q, Échap ou Ctrl+C pour arrêter le serveur.'
Write-Host ''
if (-not $SansNavigateur) { Start-Process $url }

try {
    while ($listener.IsListening) {
        $touche = $null
        try {
            if ([Console]::KeyAvailable) { $touche = [Console]::ReadKey($true) }
        } catch { }
        if ($touche -and ($touche.Key -eq 'Q' -or $touche.Key -eq 'Escape')) { break }
        Start-Sleep -Milliseconds 300
    }
} finally {
    Write-Host 'Arrêt du serveur…'
    try { $listener.Stop(); $listener.Close() } catch { }
    foreach ($t in $taches) { try { $t.PS.Dispose() } catch { } }
    try { $pool.Close(); $pool.Dispose() } catch { }
}
