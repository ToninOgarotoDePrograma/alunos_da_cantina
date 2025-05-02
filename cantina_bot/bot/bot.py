import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Union
import aiohttp
import asyncio
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

# Configuração de logging otimizada
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_cantina.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Estados da conversação
ESCOLHER_ITEM, ADICIONAR_OBSERVACOES = range(2)


class Config:
    API_BASE_URL = 'http://localhost:5000'
    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
    MAX_OBSERVACOES = 200
    HORARIO_MARMITA = {'inicio': '17:00', 'fim': '10:30'}
    CACHE_TTL = 300  # 5 minutos em segundos


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
        self._session = None
        self._cardapio_cache = {'data': None, 'timestamp': 0}
        self._setup_handlers()

    async def init_session(self):
        """Inicializa a sessão aiohttp"""
        self._session = aiohttp.ClientSession()

    async def close_session(self):
        """Fecha a sessão aiohttp"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _setup_handlers(self):
        """Configura todos os handlers do bot de forma otimizada"""
        # Handlers principais
        main_handlers = [
            CommandHandler("start", self._start),
            CommandHandler("menu", self._mostrar_menu_principal),
            CommandHandler("cardapio", self._mostrar_cardapio),
            CommandHandler("meuspedidos", self._listar_pedidos),
            CommandHandler("inscrever", self._inscrever_usuario),
            CallbackQueryHandler(self._button_handler)
        ]

        # Conversation handler otimizado
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

        self.application.add_handlers(main_handlers + [conv_handler])
        self.application.add_error_handler(self._handle_error)

    # Handlers principais otimizados
    async def _start(self, update: Update, context: CallbackContext):
        """Handler otimizado para o comando /start"""
        await self._mostrar_menu_principal(update, context,
                                           f"👋 Olá {update.effective_user.first_name}!\nBem-vindo à Cantina Digital!")

    async def _mostrar_menu_principal(self, update: Update, context: CallbackContext,
                                      texto: str = "Escolha uma opção:"):
        """Menu principal com resposta otimizada"""
        keyboard = [
            [InlineKeyboardButton("📋 Ver Cardápio", callback_data='ver_cardapio'),
             InlineKeyboardButton("🛒 Fazer Pedido", callback_data='fazer_pedido')],
            [InlineKeyboardButton("📦 Meus Pedidos", callback_data='meus_pedidos'),
             InlineKeyboardButton("📝 Inscrever-se", callback_data='inscrever')]
        ]

        await self._send_message(update, texto, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _button_handler(self, update: Update, context: CallbackContext):
        """Handler central otimizado para botões inline"""
        query = update.callback_query
        await query.answer()

        handler_map = {
            'ver_cardapio': self._mostrar_cardapio,
            'fazer_pedido': self._iniciar_pedido,
            'meus_pedidos': self._listar_pedidos,
            'inscrever': self._inscrever_usuario,
            'voltar_menu': self._mostrar_menu_principal
        }

        if query.data in handler_map:
            await handler_map[query.data](update, context)
        elif query.data.startswith('item_'):
            await self._processar_escolha_item(update, context)

    async def _mostrar_cardapio(self, update: Update, context: CallbackContext):
        """Exibe o cardápio com cache"""
        try:
            horario_marmita = await self._verificar_horario_marmita()
            keyboard = [[InlineKeyboardButton("🍔 Lanches", callback_data='cardapio_lanches')]]

            if horario_marmita:
                keyboard[0].append(InlineKeyboardButton("🍱 Marmitas", callback_data='cardapio_marmitas'))

            keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data='voltar_menu')])

            mensagem = "📋 *CARDÁPIO* 📋\n\nSelecione o tipo de cardápio:"
            if not horario_marmita:
                mensagem += f"\n\n⚠️ Marmitas disponíveis apenas das {Config.HORARIO_MARMITA['inicio']} às {Config.HORARIO_MARMITA['fim']}"

            await self._send_message(update, mensagem, reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            logger.error(f"Erro ao mostrar cardápio: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro ao carregar cardápio")

    async def _iniciar_pedido(self, update: Update, context: CallbackContext) -> int:
        """Inicia pedido com cardápio em cache"""
        try:
            context.user_data.clear()
            cardapio = await self._get_cardapio_cached()

            # Agrupa itens em colunas para melhor visualização
            keyboard = []
            for i in range(0, len(cardapio), 2):
                row = []
                for item in cardapio[i:i + 2]:
                    row.append(InlineKeyboardButton(
                        f"{item['nome']} - R${float(item['preco']):.2f}",
                        callback_data=f"item_{item['id']}"
                    ))
                keyboard.append(row)

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
        """Processa escolha do item com cache"""
        query = update.callback_query
        await query.answer()

        try:
            item_id = int(query.data.replace('item_', ''))
            cardapio = await self._get_cardapio_cached()
            item = next((i for i in cardapio if i['id'] == item_id), None)

            if not item:
                await query.edit_message_text("❌ Item não encontrado")
                return ConversationHandler.END

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
        """Finaliza pedido com requisições assíncronas"""
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

            # Envia pedido e notificação em paralelo
            response = await self._enviar_pedido_api(pedido)

            if response.status == 201:
                pedido_data = await response.json()
                mensagem = (
                    f"🎉 *Pedido #{pedido_data['id']} registrado!*\n\n"
                    f"• Item: {pedido.item_nome}\n• Preço: R$ {pedido.preco:.2f}\n"
                    f"• Observações: {pedido.observacoes or 'Nenhuma'}\n\n"
                    "Acompanhe o status com /meuspedidos"
                )

                # Envia mensagem principal e notificação em paralelo
                await asyncio.gather(
                    self._send_message(update, mensagem, parse_mode='Markdown'),
                    self._enviar_notificacao(
                        pedido.user_id,
                        f"✅ *Pedido realizado!*\nID: #{pedido_data['id']}\n"
                        f"Item: {pedido.item_nome}\nStatus: Em preparação"
                    )
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
        """Lista pedidos com paginação futura"""
        try:
            user_id = update.effective_user.id
            pedidos = await self._fetch_data('pedidos')
            meus_pedidos = [p for p in pedidos if p.get('user_id') == user_id]

            if not meus_pedidos:
                await self._send_message(update, "📭 Você não tem pedidos ativos")
                return

            status_emojis = {
                'Recebido': '🟡', 'Preparando': '🟠', 'Pronto': '🟢',
                'Entregue': '✅', 'Cancelado': '❌'
            }

            # Limita a exibição a 10 pedidos por vez
            pedidos_exibir = meus_pedidos[:10]
            mensagem = ["📦 *SEUS PEDIDOS* 📦\n"] + [
                f"\n{status_emojis.get(p.get('status', 'Recebido'), '🟡')} *Pedido #{p['id']}*\n"
                f"• Item: {p['item']}\n• Status: {p.get('status', 'Em processamento')}\n"
                f"• Data: {p.get('timestamp', '').replace('T', ' ')[:16]}\n"
                f"• Observações: {p.get('observacoes', 'Nenhuma')}"
                for p in pedidos_exibir
            ]

            if len(meus_pedidos) > 10:
                mensagem.append(
                    f"\n\nMostrando 10 de {len(meus_pedidos)} pedidos. Use /meuspedidos novamente para ver mais.")

            await self._send_message(update, "\n".join(mensagem), parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Erro ao listar pedidos: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro ao carregar pedidos")

    async def _inscrever_usuario(self, update: Update, context: CallbackContext):
        """Cadastro otimizado"""
        try:
            user = update.effective_user
            response = await self._post_data('participantes', {
                'user_id': user.id,
                'name': user.first_name,
                'username': user.username
            })

            if response.status == 201:
                await self._send_message(
                    update,
                    f"✅ *Cadastro realizado!* 🎉\n\nOlá {user.first_name}, você agora está cadastrado!\n\n"
                    "Use /pedir para fazer seu primeiro pedido.",
                    parse_mode='Markdown'
                )
            elif response.status == 409:
                await self._send_message(update, "ℹ️ Você já está cadastrado!")
            else:
                await self._send_error(update, "❌ Falha no cadastro")

        except Exception as e:
            logger.error(f"Erro no cadastro: {e}", exc_info=True)
            await self._send_error(update, "❌ Erro no cadastro")

    async def _cancelar_pedido(self, update: Update, context: CallbackContext) -> int:
        """Cancela pedido de forma otimizada"""
        context.user_data.clear()
        await self._send_message(update, "❌ Operação cancelada")
        return ConversationHandler.END

    async def _handle_error(self, update: Update, context: CallbackContext):
        """Manipulador de erros otimizado"""
        logger.error(f"Erro não tratado: {context.error}", exc_info=True)
        if update:
            await self._send_error(
                update,
                "⚠️ Ocorreu um erro inesperado\n\nPor favor, tente novamente mais tarde."
            )

    # Métodos auxiliares otimizados
    async def _verificar_horario_marmita(self) -> bool:
        """Verificação de horário otimizada"""
        try:
            agora = datetime.now().time()
            inicio = datetime.strptime(Config.HORARIO_MARMITA['inicio'], '%H:%M').time()
            fim = datetime.strptime(Config.HORARIO_MARMITA['fim'], '%H:%M').time()
            return inicio <= agora <= fim
        except Exception as e:
            logger.error(f"Erro ao verificar horário: {e}")
            return False

    async def _get_cardapio_cached(self) -> List[Dict]:
        """Obtém cardápio com cache"""
        now = time.time()
        if not self._cardapio_cache['data'] or (now - self._cardapio_cache['timestamp']) > Config.CACHE_TTL:
            self._cardapio_cache['data'] = await self._fetch_data('cardapio')
            self._cardapio_cache['timestamp'] = now
        return self._cardapio_cache['data']

    async def _fetch_data(self, endpoint: str) -> Union[Dict, List]:
        """Busca dados da API com aiohttp"""
        try:
            async with self._session.get(
                    f"{Config.API_BASE_URL}/{endpoint}",
                    timeout=Config.REQUEST_TIMEOUT
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Erro na API ({endpoint}): {e}")
            raise

    async def _post_data(self, endpoint: str, data: Dict) -> aiohttp.ClientResponse:
        """Envia dados para API com aiohttp"""
        try:
            return await self._session.post(
                f"{Config.API_BASE_URL}/{endpoint}",
                json=data,
                timeout=Config.REQUEST_TIMEOUT
            )
        except Exception as e:
            logger.error(f"Erro na API ({endpoint}): {e}")
            raise

    async def _enviar_pedido_api(self, pedido: Pedido) -> aiohttp.ClientResponse:
        """Envia pedido para API otimizado"""
        return await self._post_data('pedidos', {
            'item_id': pedido.item_id,
            'item': pedido.item_nome,
            'usuario': pedido.usuario,
            'user_id': pedido.user_id,
            'observacoes': pedido.observacoes,
            'preco': pedido.preco
        })

    async def _enviar_notificacao(self, user_id: int, mensagem: str) -> bool:
        """Envia notificação otimizada"""
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
        """Envio de mensagem otimizado"""
        try:
            if update.message:
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            elif update.callback_query:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")

    async def _send_error(self, update: Update, message: str):
        """Envio de erro otimizado"""
        await self._send_message(update, f"⚠️ {message}")


async def run_bot():
    """Função principal para executar o bot"""
    TOKEN = '7641186323:AAF-Gjca2gfprqV740SH26i1s30gOJ42wE0'
    logger.info("Iniciando bot da Cantina Digital...")

    bot = CantinaBot(TOKEN)
    await bot.init_session()

    try:
        # Cria tasks para rodar o bot e monitorar exceções
        async with bot.application:
            await bot.application.start()
            await bot.application.updater.start_polling(drop_pending_updates=True)

            # Mantém o bot rodando até que seja interrompido
            while True:
                await asyncio.sleep(3600)  # Verifica a cada hora se precisa encerrar

    except asyncio.CancelledError:
        logger.info("Recebido sinal de encerramento, desligando o bot...")
    except Exception as e:
        logger.error(f"Erro na execução do bot: {e}", exc_info=True)
    finally:
        await bot.close_session()
        logger.info("Bot encerrado corretamente")


if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)