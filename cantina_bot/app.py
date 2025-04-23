import json
import os
from datetime import datetime
from typing import List, Dict, Union

from flask import Flask, jsonify, request, abort
from flask_cors import CORS


# Configuração do Flask
app = Flask(__name__) # Cria
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', '7641186323:AAF-Gjca2gfprqV740SH26i1s30gOJ42wE0')

# Inicializa a interface web
init_app(app)
# Constantes para os arquivos JSON
DATA_DIR = 'data'#caminho

#criacao dos arquivos json no caminho
CARDAPIO_FILE = os.path.join(DATA_DIR, 'cardapio.json')
CARDAPIO_DIA_FILE = os.path.join(DATA_DIR, 'cardapio_do_dia.json')
PEDIDOS_FILE = os.path.join(DATA_DIR, 'pedidos.json')
PARTICIPANTES_FILE = os.path.join(DATA_DIR, 'participantes.json')

# Garante que o diretório de dados existe
os.makedirs(DATA_DIR, exist_ok=True)


class DataManager:
    """Classe para gerenciamento centralizado de operações com arquivos JSON"""

    @staticmethod
    def carregar_dados(arquivo: str, estrutura_padrao=None) -> Union[List, Dict]:
        """Carrega dados de um arquivo JSON com tratamento de erros robusto"""
        if estrutura_padrao is None:
            estrutura_padrao = []
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)

                # Validação básica da estrutura
                if not isinstance(dados, (list, dict)):
                    raise ValueError(f"Formato inválido em {arquivo}")

                return dados

        except FileNotFoundError:
            # Se o arquivo não existe, retorna a estrutura padrão e cria o arquivo
            DataManager.salvar_dados(arquivo, estrutura_padrao)
            return estrutura_padrao
        except (json.JSONDecodeError, ValueError) as e:
            app.logger.error(f"Erro ao carregar {arquivo}: {str(e)}")
            return estrutura_padrao

    @staticmethod
    def salvar_dados(arquivo: str, dados: Union[List, Dict]) -> None:
        """Salva dados em um arquivo JSON com formatação consistente"""
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)


# ========== ROTAS PARA CARDÁPIO ==========
@app.route('/cardapio', methods=['GET', 'POST'])
def gerenciar_cardapio():
    if request.method == 'GET':
        cardapio = DataManager.carregar_dados(CARDAPIO_FILE, [])
        return jsonify(cardapio)

    # POST - Adicionar novo item ao cardápio
    novo_item = request.get_json()

    # Validação dos dados
    if not novo_item or not all(key in novo_item for key in ['nome', 'preco']):
        abort(400, description="Dados incompletos. Campos obrigatórios: 'nome', 'preco'")

    try:
        # Converte preço para float e valida
        novo_item['preco'] = float(novo_item['preco'])
        if novo_item['preco'] <= 0:
            raise ValueError("Preço deve ser positivo")
    except (ValueError, TypeError):
        abort(400, description="Preço inválido. Deve ser um número positivo")

    # Carrega e valida cardápio existente
    cardapio = DataManager.carregar_dados(CARDAPIO_FILE, [])

    # Verifica se item já existe (case insensitive)
    if any(item['nome'].lower() == novo_item['nome'].lower() for item in cardapio):
        abort(409, description="Item já existe no cardápio")

    # Adiciona ID único ao novo item
    novo_id = max(item.get('id', 0) for item in cardapio) + 1 if cardapio else 1
    novo_item['id'] = novo_id

    cardapio.append(novo_item)
    DataManager.salvar_dados(CARDAPIO_FILE, cardapio)

    return jsonify(novo_item), 201


# ========== ROTAS PARA PEDIDOS ==========
@app.route('/pedidos', methods=['GET', 'POST'])
def gerenciar_pedidos():
    if request.method == 'GET':
        pedidos = DataManager.carregar_dados(PEDIDOS_FILE, [])
        return jsonify(pedidos)

    # POST - Criar novo pedido
    novo_pedido = request.get_json()

    # Validação dos dados
    campos_obrigatorios = ['item_id', 'usuario', 'user_id', 'quantidade']
    if not novo_pedido or not all(key in novo_pedido for key in campos_obrigatorios):
        abort(400, description=f"Dados incompletos. Campos obrigatórios: {', '.join(campos_obrigatorios)}")

    try:
        novo_pedido['quantidade'] = int(novo_pedido['quantidade'])
        if novo_pedido['quantidade'] <= 0:
            raise ValueError("Quantidade deve ser positiva")
    except (ValueError, TypeError):
        abort(400, description="Quantidade inválida. Deve ser um número inteiro positivo")

    # Verifica se o item existe no cardápio
    cardapio = DataManager.carregar_dados(CARDAPIO_FILE, [])
    item_existe = any(item.get('id') == novo_pedido['item_id'] for item in cardapio)

    if not item_existe:
        abort(404, description="Item não encontrado no cardápio")

    # Cria o pedido com dados completos
    pedidos = DataManager.carregar_dados(PEDIDOS_FILE, [])
    novo_id = max(pedido.get('id', 0) for pedido in pedidos) + 1 if pedidos else 1

    pedido_completo = {
        'id': novo_id,
        'item_id': novo_pedido['item_id'],
        'usuario': novo_pedido['usuario'],
        'user_id': novo_pedido['user_id'],
        'quantidade': novo_pedido['quantidade'],
        'timestamp': datetime.now().isoformat(),
        'status': 'Recebido',
        'observacoes': novo_pedido.get('observacoes', '')
    }

    pedidos.append(pedido_completo)
    DataManager.salvar_dados(PEDIDOS_FILE, pedidos)

    return jsonify(pedido_completo), 201


@app.route('/pedidos/<int:pedido_id>', methods=['GET', 'PATCH', 'DELETE'])
def gerenciar_pedido(pedido_id):
    pedidos = DataManager.carregar_dados(PEDIDOS_FILE, [])
    pedido = next((p for p in pedidos if p.get('id') == pedido_id), None)

    if not pedido:
        abort(404, description="Pedido não encontrado")

    if request.method == 'GET':
        return jsonify(pedido)

    elif request.method == 'PATCH':
        dados_atualizacao = request.get_json()

        # Valida campos que podem ser atualizados
        campos_permitidos = ['status', 'observacoes']
        if not all(key in campos_permitidos for key in dados_atualizacao.keys()):
            abort(400, description=f"Apenas os campos {', '.join(campos_permitidos)} podem ser atualizados")

        # Atualiza o pedido
        pedido.update(dados_atualizacao)
        DataManager.salvar_dados(PEDIDOS_FILE, pedidos)

        return jsonify(pedido)

    elif request.method == 'DELETE':
        pedidos = [p for p in pedidos if p.get('id') != pedido_id]
        DataManager.salvar_dados(PEDIDOS_FILE, pedidos)
        return jsonify({"message": "Pedido removido com sucesso"}), 200


# ========== ROTAS PARA PARTICIPANTES ==========
@app.route('/participantes', methods=['GET', 'POST'])
def gerenciar_participantes():
    if request.method == 'GET':
        participantes = DataManager.carregar_dados(PARTICIPANTES_FILE, [])
        return jsonify(participantes)

    # POST - Adicionar novo participante
    novo_participante = request.get_json()

    # Validação e normalização dos dados
    if 'name' in novo_participante:
        novo_participante['nome'] = novo_participante.pop('name')
    if 'user_id' in novo_participante:
        novo_participante['telegram_id'] = novo_participante.pop('user_id')

    campos_obrigatorios = ['nome', 'telegram_id']
    if not novo_participante or not all(key in novo_participante for key in campos_obrigatorios):
        abort(400, description=f"Dados incompletos. Campos obrigatórios: {', '.join(campos_obrigatorios)}")

    # Verifica se participante já existe
    participantes = DataManager.carregar_dados(PARTICIPANTES_FILE, [])
    if any(p['telegram_id'] == novo_participante['telegram_id'] for p in participantes):
        abort(409, description="Participante já cadastrado")

    # Adiciona ID único
    novo_id = max(p.get('id', 0) for p in participantes) + 1 if participantes else 1
    novo_participante['id'] = novo_id

    participantes.append(novo_participante)
    DataManager.salvar_dados(PARTICIPANTES_FILE, participantes)

    return jsonify(novo_participante), 201


# ========== ROTA PARA CARDÁPIO DO DIA ==========
@app.route('/cardapio-do-dia', methods=['GET', 'POST', 'PUT'])
def gerenciar_cardapio_dia():
    if request.method == 'GET':
        cardapio_dia = DataManager.carregar_dados(CARDAPIO_DIA_FILE, {"marmita": []})
        return jsonify(cardapio_dia)

    # POST/PUT - Atualizar cardápio do dia
    dados = request.get_json()

    if 'marmita' not in dados:
        abort(400, description="Campo 'marmita' é obrigatório")

    # Normaliza os dados (aceita string ou lista)
    if isinstance(dados['marmita'], str):
        marmita = [item.strip() for item in dados['marmita'].split('\n') if item.strip()]
    elif isinstance(dados['marmita'], list):
        marmita = [item.strip() for item in dados['marmita'] if item.strip()]
    else:
        abort(400, description="Campo 'marmita' deve ser string ou lista")

    # Salva o novo cardápio
    novo_cardapio = {
        "marmita": marmita,
        "atualizado_em": datetime.now().isoformat()
    }

    DataManager.salvar_dados(CARDAPIO_DIA_FILE, novo_cardapio)

    return jsonify(novo_cardapio), 200


# ========== CONFIGURAÇÃO DE ERROS ==========
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Requisição inválida", "message": str(error)}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Não encontrado", "message": str(error)}), 404


@app.errorhandler(409)
def conflict(error):
    return jsonify({"error": "Conflito", "message": str(error)}), 409


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Erro interno do servidor", "message": "Ocorreu um erro inesperado"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)