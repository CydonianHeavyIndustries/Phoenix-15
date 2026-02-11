$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$dockerfile = Join-Path $PSScriptRoot "docker\\Dockerfile"
$imageName = "phoenix-15-os"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker not found. Install Docker Desktop first."
  exit 1
}

docker image inspect $imageName *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Building Docker image $imageName..."
  docker build -t $imageName -f $dockerfile $repo
}

Write-Host "Building Phoenix-15 ISO..."
docker run --rm -e PHX_ROOT=/work -v "${repo}:/work" $imageName /work/os/docker/build.sh

Write-Host "Done. ISO output: os\\out\\phoenix-15.iso"
