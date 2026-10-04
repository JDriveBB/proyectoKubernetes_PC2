[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot

# Las imagenes se construyen CONTRA EL DEMONIO DOCKER DE MINIKUBE, no contra el
# de la maquina. Asi quedan dentro del cluster sin pasar por
# 'minikube image load', que no reemplaza un tag que ya existe: al reconstruir
# una imagen, el cluster seguiria ejecutando la version anterior y los cambios
# no se verian por ninguna parte.
Write-Host 'Apuntando Docker al demonio de Minikube...'
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
if ($LASTEXITCODE -ne 0) { throw 'No se pudo conectar con el demonio Docker de Minikube. Esta arriba el cluster?' }

@('python', 'java', 'c') | ForEach-Object {
    $lenguaje = $_
    $tag = "kubernates-202630-$lenguaje`:1.0"
    Write-Host "Construyendo $tag..."
    docker build -t $tag (Join-Path $raiz "imagenes/$lenguaje")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo construir $tag" }
}

Write-Host ''
Write-Host 'Imagenes disponibles dentro de Minikube:'
docker images --filter 'reference=kubernates-202630-*' --format '  {{.Repository}}:{{.Tag}}  {{.ID}}  {{.CreatedSince}}'
