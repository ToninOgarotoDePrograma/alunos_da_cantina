from flask import Flask, render_template, jsonify, request
import requests
from datetime import datetime
import json

app = Flask(__name__)

# Configurações
API_BASE = "http://localhost:5000"
TELEGRAM_TOKEN = "7641186323:AAF-Gjca2gfprqV740SH26i1s30gOJ42wE0"


@app.route('/')
def index():
    return render_template('../webInterface/index.html')


# API endpoints para a interface web
@app.route('/pedidos')
def get_pedidos():
    try:
        response = requests.get(f"{API_BASE}/pedidos")
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route('/cardapio')
def get_cardapio():
    try:
        response = requests.get(f"{API_BASE}/cardapio")
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route('/cardapio-do-dia')
def get_cardapio_dia():
    try:
        response = requests.get(f"{API_BASE}/cardapio-do-dia")
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route('/atualizar-status/<int:pedido_id>', methods=['POST'])
def atualizar_status(pedido_id):
    try:
        novo_status = request.json.get('status')
        response = requests.patch(
            f"{API_BASE}/pedidos/{pedido_id}",
            json={'status': novo_status}
        )
        response.raise_for_status()

        # Se foi marcado como pronto, enviar notificação
        if novo_status == 'Pronto':
            pedido = requests.get(f"{API_BASE}/pedidos/{pedido_id}").json()
            enviar_notificacao_telegram(pedido['user_id'], f"✅ Seu pedido #{pedido_id} está pronto para retirada!")

        return jsonify({"success": True})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route('/notificar-todos', methods=['POST'])
def notificar_todos():
    try:
        mensagem = request.json.get('mensagem')
        participantes = requests.get(f"{API_BASE}/participantes").json()

        for p in participantes:
            if p.get('telegram_id'):
                enviar_notificacao_telegram(p['telegram_id'], f"📢 Mensagem da Cantina:\n{mensagem}")

        return jsonify({"success": True, "enviados": len(participantes)})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


def enviar_notificacao_telegram(chat_id, mensagem):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': mensagem,
                'parse_mode': 'Markdown'
            },
            timeout=5
        )
    except:
        pass


if __name__ == '__main__':
    app.run(port=5001, debug=True)