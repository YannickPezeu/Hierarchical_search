# Étape 1: Choisir une image de base Python légère et officielle.
FROM python:3.11-slim

# Étape 2: Définir le répertoire de travail dans le conteneur.
WORKDIR /app

# Étape 3: Mettre à jour pip et installer les dépendances.
# On copie d'abord requirements.txt pour profiter du cache de Docker.
# Cette étape ne sera ré-exécutée que si le fichier change.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Étape 4: Copier le code source de l'application.
# On ne copie que le dossier 'src' qui contient toute la logique.
COPY ./src ./src

# Étape 5: Exposer le port sur lequel l'application va écouter.
EXPOSE 8000

# Étape 6: Définir la commande pour lancer l'application.
# Uvicorn est le serveur ASGI qui exécute notre application FastAPI.
# L'hôte 0.0.0.0 est nécessaire pour que le conteneur soit accessible de l'extérieur.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
