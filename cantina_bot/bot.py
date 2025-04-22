import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, List, Union
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_cantina.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Estados da conversação
ESCOLHER_ITEM, ADICIONAR_OBSERVACOES = range(2)


class Config:
    API_BASE_URL = 'http://localhost:5000'
    REQUEST_TIMEOUT = 10
    MAX_OBSERVACOES = 200
    HORARIO_MARMITA = {'inicio': '11:00', 'fim': '13:30'}


@dataclass
class ItemCardapio:
    id: int
    nome: str
    preco: float
    tipo: str = 'lanche'


@dataclass
class Pedido:
    id: Optional[int] = None
    item_id: Optional[int] = None
    item_nome: Optional[str] = None
    preco: Optional[float] = None
    usuario: Optional[str] = None
    user_id: Optional[int] = None
    observacoes: Optional[str] = None
    status: str = 'Recebido'
    timestamp: Optional[str] = None


class CantinaBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Configura todos os handlers do bot"""
        self.application.add_handler(CallbackQueryHandler(self._button_handler))

        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('pedir', self._iniciar_pedido),
                CallbackQueryHandler(self._iniciar_pedido, pattern='^fazer_pedido$')
            ],
            states={
                ESCOLHER_ITEM: [CallbackQueryHandler(self._processar_escolha_item)],
                ADICIONAR_OBSERVACOES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._finalizar_pedido)
                ],
            },
            fallbacks=[
                CommandHandler('cancelar', self._cancelar_pedido),
                CallbackQueryHandler(self._cancelar_pedido, pattern='^cancelar$')
            ],
            allow_reentry=True
        )
        self.application.add_handler(conv_handler)

        handlers = [
            CommandHandler("start", self._start),
            CommandHandler("cardapio", self._mostrar_cardapio),
            CommandHandler("menu", self._mostrar_menu_principal),
            CommandHandler("meuspedidos", self._listar_pedidos),
            CommandHandler("inscrever", self._inscrever_usuario),
        ]
        for handler in handlers:
            self.application.add_handler(handler)

        self.application.add_error_handler(self._handle_error)

    # Handlers principais
    async def _start(self, update: Update, context: CallbackContext):
        """Handler para o comando /start"""
        user = update.effective_user
        await self._mostrar_menu_principal(update, context,
                                           f"👋 Olá {user.first_name}!\nBem-vindo à Cantina Digital!")

    async def _mostrar_menu_principal(self, update: Update, context: CallbackContext,
                                      texto: str = "Escolha uma opção:"):
        """Mostra o menu principal com botões inline"""
        keyboard = [
            [InlineKeyboardButton("📋 Ver Cardápio", callback_data='ver_cardapio')],
            [InlineKeyboardButton("🛒 Fazer Pedido", callback_data='fazer_pedido')],
            [InlineKeyboardButton("📦 Meus Pedidos", callback_data='meus_pedidos')],
            [InlineKeyboardButton("📝 Inscrever-se", callback_data='inscrever')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(texto, reply_markup=reply_markup)
        elif update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(texto, reply_markup=reply_markup)

    async def _button_handler(self, update: Update, context: CallbackContext):
        """Handler central para todos os botões inline"""
        query = update.callback_query
        await query.answer()

        try:
            if query.data == 'ver_cardapio':
                await self._mostrar_cardapio(update, context)
            elif query.data == 'fazer_pedido':
                await self._iniciar_pedido(update, context)
            elif query.data == 'meus_pedidos':
                await self._listar_pedidos(update, context)
            elif query.data == 'inscrever':
                await self._inscrever_usuario(update, context)
            elif query.data == 'voltar_menu':
                await self._mostrar_menu_principal(update, context)
            elif query.data.startswith('item_'):
                await self._processar_escolha_item(update, context)

        except Exception as e:
            logger.error(f"Erro no button_handler: {e}", exc_info=True)
            await self._send_error(update, "❌ Ocorreu um erro ao processar sua ação")

    async def _mostrar_cardapio(self, update: Update, context: CallbackContext):
        """Exibe o cardápio com abas para lanches e marmitas"""
        try:
            # Verifica se está no horário de marmita
            horario_marmita = await self._verificar_horario_marmita()

            keyboard = [
                [InlineKeyboardButton("🍔 Lanches", callback_data='cardapio_lanches')]
            ]

            if horario_marmita:
                keyboard[0].append(InlineKeyboardButton("🍱 Marmitas", callback_data='cardapio_marmitas'))

            keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data='voltar_menu')])

            reply_markup = InlineKeyboardMarkup(keyboard)

            mensagem = "📋 *CARDÁPIO* 📋\n\nSelecione o tipo de cardápio:"
            if not horario_marmita:
                mensagem += "\n\n⚠️ Marmitas disponíveis apenas das {} às {}".format(
                    Config.HORARIO_MARMITA['inicio'],
                    Config.HORARIO_MARMITA['fim']
                )

            await self._send_message(
                update,
                mensagem,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Erro ao mostrar cardápio: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro ao carregar cardápio")

    async def _iniciar_pedido(self, update: Update, context: CallbackContext) -> int:
        """Inicia o processo de pedido"""
        try:
            # Limpa dados anteriores
            context.user_data.clear()

            # Cria teclado com itens do cardápio
            cardapio = await self._fetch_data('cardapio')
            keyboard = []

            for item in cardapio:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{item['nome']} - R${float(item['preco']):.2f}",
                        callback_data=f"item_{item['id']}"
                    )
                ])

            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data='cancelar')])

            await self._send_message(
                update,
                "🍽️ *FAZER PEDIDO*\n\nEscolha um item do cardápio:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

            return ESCOLHER_ITEM

        except Exception as e:
            logger.error(f"Erro ao iniciar pedido: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro ao iniciar pedido")
            return ConversationHandler.END

    async def _processar_escolha_item(self, update: Update, context: CallbackContext) -> int:
        """Processa a escolha do item pelo usuário"""
        query = update.callback_query
        await query.answer()

        try:
            item_id = int(query.data.replace('item_', ''))
            cardapio = await self._fetch_data('cardapio')
            item = next((i for i in cardapio if i['id'] == item_id), None)

            if not item:
                await query.edit_message_text("❌ Item não encontrado")
                return ConversationHandler.END

            # Armazena o item selecionado
            context.user_data['pedido'] = Pedido(
                item_id=item['id'],
                item_nome=item['nome'],
                preco=float(item['preco']),
                usuario=query.from_user.first_name,
                user_id=query.from_user.id
            )

            await query.edit_message_text(
                f"✅ *Item selecionado:* {item['nome']} - R$ {float(item['preco']):.2f}\n\n"
                "📝 Por favor, digite suas observações (ou 'ok' para continuar sem observações):",
                parse_mode='Markdown'
            )

            return ADICIONAR_OBSERVACOES

        except Exception as e:
            logger.error(f"Erro ao processar item: {e}", exc_info=True)
            await query.edit_message_text("❌ Erro ao processar item")
            return ConversationHandler.END

    async def _finalizar_pedido(self, update: Update, context: CallbackContext) -> int:
        """Finaliza o processo de pedido"""
        try:
            pedido = context.user_data.get('pedido')
            if not pedido:
                await self._send_message(update, "❌ Pedido não encontrado")
                return ConversationHandler.END

            observacoes = update.message.text.strip()
            if observacoes.lower() != 'ok':
                if len(observacoes) > Config.MAX_OBSERVACOES:
                    await self._send_message(
                        update,
                        f"⚠️ Observações muito longas (máx. {Config.MAX_OBSERVACOES} caracteres)"
                    )
                    return ADICIONAR_OBSERVACOES
                pedido.observacoes = observacoes

            # Envia pedido para API
            response = await self._enviar_pedido_api(pedido)

            if response.status_code == 201:
                pedido_data = response.json()
                await self._send_message(
                    update,
                    f"🎉 *Pedido #{pedido_data['id']} registrado!*\n\n"
                    f"• Item: {pedido.item_nome}\n"
                    f"• Preço: R$ {pedido.preco:.2f}\n"
                    f"• Observações: {pedido.observacoes or 'Nenhuma'}\n\n"
                    "Acompanhe o status com /meuspedidos",
                    parse_mode='Markdown'
                )

                # Envia notificação
                await self._enviar_notificacao(
                    pedido.user_id,
                    f"✅ *Pedido realizado!*\nID: #{pedido_data['id']}\n"
                    f"Item: {pedido.item_nome}\n"
                    f"Status: Em preparação"
                )
            else:
                await self._send_error(update, "❌ Falha ao registrar pedido")

        except Exception as e:
            logger.error(f"Erro ao finalizar pedido: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro ao finalizar pedido")

        finally:
            context.user_data.clear()
            return ConversationHandler.END

    async def _listar_pedidos(self, update: Update, context: CallbackContext):
        """Lista os pedidos do usuário"""
        try:
            user_id = update.effective_user.id
            pedidos = await self._fetch_data('pedidos')
            meus_pedidos = [p for p in pedidos if p.get('user_id') == user_id]

            if not meus_pedidos:
                await self._send_message(update, "📭 Você não tem pedidos ativos")
                return

            mensagem = ["📦 *SEUS PEDIDOS* 📦\n"]
            for pedido in meus_pedidos:
                status_emoji = {
                    'Recebido': '🟡',
                    'Preparando': '🟠',
                    'Pronto': '🟢',
                    'Entregue': '✅',
                    'Cancelado': '❌'
                }.get(pedido.get('status', 'Recebido'), '🟡')

                mensagem.append(
                    f"\n{status_emoji} *Pedido #{pedido['id']}*\n"
                    f"• Item: {pedido['item']}\n"
                    f"• Status: {pedido.get('status', 'Em processamento')}\n"
                    f"• Data: {pedido.get('timestamp', '').replace('T', ' ')[:16]}\n"
                    f"• Observações: {pedido.get('observacoes', 'Nenhuma')}"
                )

            await self._send_message(update, "\n".join(mensagem), parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Erro ao listar pedidos: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro ao carregar pedidos")

    async def _inscrever_usuario(self, update: Update, context: CallbackContext):
        """Registra o usuário no sistema"""
        try:
            user = update.effective_user
            response = await self._post_data('participantes', {
                'user_id': user.id,
                'name': user.first_name,
                'username': user.username
            })

            if response.status_code == 201:
                await self._send_message(
                    update,
                    f"✅ *Cadastro realizado!* 🎉\n\n"
                    f"Olá {user.first_name}, você agora está cadastrado!\n\n"
                    "Use /pedir para fazer seu primeiro pedido.",
                    parse_mode='Markdown'
                )
            elif response.status_code == 409:
                await self._send_message(update, "ℹ️ Você já está cadastrado!")
            else:
                await self._send_error(update, "❌ Falha no cadastro")

        except Exception as e:
            logger.error(f"Erro no cadastro: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro no cadastro")

    async def _cancelar_pedido(self, update: Update, context: CallbackContext) -> int:
        """Cancela o processo de pedido"""
        context.user_data.clear()
        await self._send_message(update, "❌ Operação cancelada")
        return ConversationHandler.END

    async def _handle_error(self, update: Update, context: CallbackContext):
        """Manipulador de erros"""
        logger.error(f"Erro não tratado: {context.error}", exc_info=True)
        await self._send_error(
            update,
            "⚠️ Ocorreu um erro inesperado\n\n"
            "Por favor, tente novamente mais tarde."
        )

    # Métodos auxiliares
    async def _verificar_horario_marmita(self) -> bool:
        """Verifica se está no horário de venda de marmitas"""
        try:
            agora = datetime.now().time()
            inicio = datetime.strptime(Config.HORARIO_MARMITA['inicio'], '%H:%M').time()
            fim = datetime.strptime(Config.HORARIO_MARMITA['fim'], '%H:%M').time()
            return inicio <= agora <= fim
        except Exception as e:
            logger.error(f"Erro ao verificar horário: {e}")
            return False

    async def _fetch_data(self, endpoint: str) -> Union[dict, list]:
        """Busca dados da API"""
        try:
            response = requests.get(
                f"{Config.API_BASE_URL}/{endpoint}",
                timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na API ({endpoint}): {e}")
            raise

    async def _post_data(self, endpoint: str, data: dict) -> requests.Response:
        """Envia dados para a API"""
        try:
            response = requests.post(
                f"{Config.API_BASE_URL}/{endpoint}",
                json=data,
                timeout=Config.REQUEST_TIMEOUT
            )
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na API ({endpoint}): {e}")
            raise

    async def _enviar_pedido_api(self, pedido: Pedido) -> requests.Response:
        """Envia pedido para a API"""
        return await self._post_data('pedidos', {
            'item_id': pedido.item_id,
            'item': pedido.item_nome,
            'usuario': pedido.usuario,
            'user_id': pedido.user_id,
            'observacoes': pedido.observacoes,
            'preco': pedido.preco
        })

    async def _enviar_notificacao(self, user_id: int, mensagem: str) -> bool:
        """Envia notificação via Telegram"""
        try:
            await self.application.bot.send_message(
                chat_id=user_id,
                text=mensagem,
                parse_mode='Markdown'
            )
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            return False

    async def _send_message(self, update: Update, text: str,
                            reply_markup=None, parse_mode=None):
        """Envia mensagem tratando diferentes tipos de update"""
        try:
            if update.message:
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            elif update.callback_query:
                query = update.callback_query
                await query.answer()
                await query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")

    async def _send_error(self, update: Update, message: str):
        """Envia mensagem de erro"""
        await self._send_message(update, f"⚠️ {message}")


def main():
    """Ponto de entrada do bot"""
    try:
        TOKEN = '7641186323:AAF-Gjca2gfprqV740SH26i1s30gOJ42wE0'  # Substitua pelo token real
        logger.info("Iniciando bot da Cantina Digital...")
        bot = CantinaBot(TOKEN)
        bot.application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Erro na inicialização: {e}", exc_info=True)


if __name__ == '__main__':
    main()