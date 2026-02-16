import requests
import socket

# Les 3 adresses à tester
urls_to_test = [
    "http://127.0.0.1:8079",      # Localhost pur
    "http://192.168.1.199:8079",  # Votre IP Wi-Fi (Network)
    "http://172.27.192.1:8079",   # Votre Passerelle WSL
    "http://host.docker.internal:8079" # Docker magic (au cas où)
]

print("🔍 DIAGNOSTIC RÉSEAU VERS LE BACKEND RAG")
print("="*50)

for url in urls_to_test:
    print(f"Testing: {url} ...", end=" ")
    try:
        # On tente juste de récupérer la doc de l'API (endpoint public)
        # ou juste vérifier si le port répond (timeout court de 2s)
        response = requests.get(f"{url}/docs", timeout=2)
        if response.status_code == 200:
            print("✅ SUCCÈS ! (Utilisez cette URL)")
        else:
            print(f"⚠️  Connecté mais erreur HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ ÉCHEC CONNEXION (Refusé/Introuvable)")
    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")

print("="*50)