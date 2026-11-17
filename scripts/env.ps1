<#
.SYNOPSIS
  Synchronise les fichiers .env.<environnement> avec les GitHub Environments du dépôt.

.DESCRIPTION
  Toute la configuration (mots de passe compris) est stockée en VARIABLES d'Environment,
  pas en secrets : GitHub ne laisse jamais relire un secret, alors qu'une variable se
  relit avec `gh`. C'est ce qui permet de recréer .env.dev, .env.test ou .env.prod sur
  n'importe quel poste et depuis n'importe quelle branche, puis de simuler un
  déploiement avec l'image publiée sur ghcr.io. Voir README, « Variables d'environnement ».

  Prérequis : gh (GitHub CLI) connecté avec un compte qui a accès au dépôt.

.EXAMPLE
  .\scripts\env.ps1 pull production    # GitHub Environment "production" -> .env.prod
  .\scripts\env.ps1 push production    # .env.prod -> GitHub Environment "production" (le crée au besoin)

  Environments GitHub : development, test, production. Fichiers locaux : .env.dev,
  .env.test, .env.prod (mêmes suffixes que docker-compose.<dev|test|prod>.yml).
#>
param(
    [Parameter(Mandatory)][ValidateSet("pull", "push")][string]$Action,
    [Parameter(Mandatory)][ValidateSet("development", "test", "production")][string]$Environment
)

$ErrorActionPreference = "Stop"
$repo = "Golem953/eligibilite-livraison-express"
$suffix = @{ development = "dev"; test = "test"; production = "prod" }[$Environment]
$file = Join-Path (Split-Path $PSScriptRoot -Parent) ".env.$suffix"

if ($Action -eq "push") {
    if (-not (Test-Path $file)) { throw "$file introuvable." }
    gh api --method PUT "repos/$repo/environments/$Environment" --silent
    if ($LASTEXITCODE -ne 0) { throw "Impossible de créer l'Environment $Environment." }
    gh variable set --repo $repo --env $Environment --env-file $file
    if ($LASTEXITCODE -ne 0) { throw "Échec de l'envoi des variables." }
    Write-Host "$file envoyé dans le GitHub Environment '$Environment'."
    return
}

# Formatage en PowerShell, pas en --jq : PowerShell 5.1 retire les guillemets passés à gh.
$json = gh variable list --repo $repo --env $Environment --json name,value
if ($LASTEXITCODE -ne 0) { throw "Impossible de lire l'Environment $Environment." }
$lines = ($json | Out-String | ConvertFrom-Json) | ForEach-Object { "$($_.name)=$($_.value)" }
if (-not $lines) { throw "L'Environment '$Environment' n'a aucune variable." }
$header = "# Généré par scripts/env.ps1 depuis le GitHub Environment '$Environment' : ne pas modifier ici, modifier sur GitHub puis relancer pull."
# UTF-8 sans BOM : Compose lirait sinon un premier nom de variable corrompu.
[IO.File]::WriteAllLines($file, @($header) + @($lines), [Text.UTF8Encoding]::new($false))
Write-Host "$file écrit ($(@($lines).Count) variables)."
