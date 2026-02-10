# Définition de l'image
$imageName = "ic-registry.epfl.ch/mr-pezeu/hierarchical-search-engine"
$deploymentName = "hierarchical-search-deployment"

Write-Host "--- Début du processus de déploiement ---" -ForegroundColor Cyan

# 1. Build de l'image Docker
Write-Host "[1/3] Construction de l'image Docker..." -ForegroundColor Yellow
docker build -t $imageName .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Le build Docker a échoué."
    exit $LASTEXITCODE
}

# 2. Push de l'image vers le registry
Write-Host "[2/3] Push de l'image vers le registry..." -ForegroundColor Yellow
docker push $imageName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Le push vers le registry a échoué."
    exit $LASTEXITCODE
}

# 3. Redémarrage du déploiement sur Kubernetes
Write-Host "[3/3] Redémarrage du déploiement Kubernetes..." -ForegroundColor Yellow
kubectl rollout restart deployment $deploymentName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Le restart du déploiement a échoué."
    exit $LASTEXITCODE
}

Write-Host "--- Déploiement terminé avec succès ! ---" -ForegroundColor Green