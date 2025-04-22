import requests
from flask import current_app

def fetch_from_api(endpoint):
    """Faz requisições para a API interna"""
    try:
        response = requests.get(f"{current_app.config['API_BASE_URL']}{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erro ao acessar API: {str(e)}")
        return None