import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
import requests
import json
from datetime import datetime, time
from tkinter import Toplevel, Label, Frame
from threading import Thread
import queue
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import time as time_module
import os
import webbrowser
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

# Configurações globais
API_BASE = "http://localhost:5000"
TELEGRAM_TOKEN = "7641186323:AAF-Gjca2gfprqV740SH26i1s30gOJ42wE0"
TEMPO_ATUALIZACAO = 15  # segundos
HORARIO_MARMITA_INICIO = time(11, 0)
HORARIO_MARMITA_FIM = time(13, 30)

# Configurações globais de cores - Versão corrigida
COR_PRIMARIA = "#2c3e50"       # Azul escuro (para cabeçalhos e elementos principais)
COR_SECUNDARIA = "#3498db"     # Azul médio (para botões e destaques)
COR_TERCIARIA = "#f8f9fa"      # Branco suave (para fundos claros)
COR_TEXTO = "#212529"          # Preto suave (para texto em fundos claros)
COR_TEXTO_ESCURO = "#f8f9fa"   # Branco (para texto em fundos escuros)
COR_FUNDO = "#ffffff"          # Branco puro (fundo principal)
COR_BOTAO = "#007bff"          # Azul vibrante (para botões primários)
COR_SUCESSO = "#28a745"        # Verde (para operações bem sucedidas)
COR_ERRO = "#dc3545"           # Vermelho (para erros)
COR_AVISO = "#ffc107"          # Amarelo (para avisos)
COR_BORDA = "#dee2e6"          # Cinza claro (para bordas)


@dataclass
class Pedido:
    id: int
    usuario: str
    item: str
    observacoes: str
    status: str
    timestamp: str
    user_id: Optional[int] = None


@dataclass
class ItemCardapio:
    nome: str
    preco: float


class ModernTooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.x = self.y = 0
        self.bgcolor = "#ffffe0"
        self.fgcolor = "#333333"
        self.font = ("Segoe UI", 9)

    def showtip(self, text):
        if self.tipwindow or not text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=self.bgcolor)

        # Adiciona sombra
        tw.wm_attributes("-alpha", 0.95)

        label = Label(tw, text=text, justify='left',
                      background=self.bgcolor, foreground=self.fgcolor,
                      relief='solid', borderwidth=1, padx=8, pady=4,
                      font=self.font, wraplength=300)
        label.pack()

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


class AdminInterface:
    def __init__(self, root):
        self.root = root
        self.pedidos: List[Pedido] = []
        self.cardapio: List[ItemCardapio] = []
        self.cardapio_do_dia: List[str] = []
        self.fila_tarefas = queue.Queue()
        self.canvas = None
        self.setup_ui()
        self.carregar_estilos()
        self.iniciar_thread_atualizacao()
        self.verificar_tarefas_pendentes()
        self.atualizar_tudo()

        # Configurar evento para redimensionamento
        self.root.bind("<Configure>", self.on_window_resize)

    def setup_ui(self):
        self.root.title("🍽️ Painel Administrativo - Cantina Digital")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.fechar_aplicacao)

        # Configurar ícone (se disponível)
        try:
            img = Image.open('icon.png') if os.path.exists('icon.png') else None
            if img:
                self.root.iconphoto(True, ImageTk.PhotoImage(img))
        except:
            pass

        # Barra de status
        self.status_bar = ttk.Label(self.root, text="Conectando ao servidor...", relief='sunken')
        self.status_bar.pack(side='bottom', fill='x', padx=2, pady=2)

        # Barra de ferramentas superior
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(side='top', fill='x', padx=5, pady=5)

        # Botões da barra de ferramentas
        self.create_toolbar_buttons()

        # Notebook principal
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=(0, 5))

        # Abas
        self.setup_aba_pedidos()
        self.setup_aba_historico()
        self.setup_aba_ferramentas()
        self.setup_aba_cardapio()
        self.setup_aba_configuracoes()
        self.setup_aba_dashboard()

        # Barra de progresso para operações
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')

        # Menu de contexto
        self.setup_context_menu()

    def create_toolbar_buttons(self):
        buttons = [
            ("🔄 Atualizar", lambda: self.executar_tarefa(self.atualizar_tudo), "Atualizar todos os dados"),
            ("📤 Exportar", self.exportar_dados, "Exportar dados para arquivo"),
            ("📊 Estatísticas", self.mostrar_estatisticas, "Mostrar estatísticas"),
            ("🔔 Notificar", self.notificar_todos, "Notificar todos os clientes"),
            ("❓ Ajuda", self.show_help, "Ajuda e informações")
        ]

        for text, command, tooltip in buttons:
            btn = ttk.Button(self.toolbar, text=text, command=command)
            btn.pack(side='left', padx=2)
            self.create_tooltip(btn, tooltip)

    def setup_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copiar", command=self.copy_to_clipboard)
        self.context_menu.add_command(label="Atualizar", command=lambda: self.executar_tarefa(self.atualizar_tudo))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ajuda", command=self.show_help)

        # Vincular menu de contexto a todos os widgets de texto
        self.root.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_to_clipboard(self):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Entry) or isinstance(widget, tk.Text):
            self.root.clipboard_clear()
            if widget.selection_present():
                self.root.clipboard_append(widget.selection_get())
            else:
                self.root.clipboard_append(widget.get())

    def setup_aba_pedidos(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📋 Pedidos Ativos")

        # Filtros
        filtro_frame = ttk.Frame(frame)
        filtro_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(filtro_frame, text="🔍 Filtrar:").pack(side='left')
        self.filtro_entry = ttk.Entry(filtro_frame, width=30)
        self.filtro_entry.pack(side='left', padx=5)
        self.filtro_entry.bind("<KeyRelease>", lambda e: self.aplicar_filtros())

        ttk.Label(filtro_frame, text="📊 Status:").pack(side='left', padx=10)
        self.status_filter = ttk.Combobox(filtro_frame,
                                          values=["Todos", "Recebido", "Preparando", "Pronto", "Entregue", "Cancelado"])
        self.status_filter.set("Todos")
        self.status_filter.pack(side='left', padx=5)
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtros())

        # Treeview de pedidos
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.pedidos_tree = ttk.Treeview(tree_frame, columns=('ID', 'Cliente', 'Item', 'Status', 'Hora'),
                                         show='headings')

        colunas = [
            ('ID', 70, 'center'),
            ('Cliente', 150, 'w'),
            ('Item', 200, 'w'),
            ('Status', 120, 'center'),
            ('Hora', 120, 'center')
        ]

        for col, width, anchor in colunas:
            self.pedidos_tree.heading(col, text=col)
            self.pedidos_tree.column(col, width=width, anchor=anchor)

        scroll_y = ttk.Scrollbar(tree_frame, orient='vertical', command=self.pedidos_tree.yview)
        scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.pedidos_tree.xview)
        self.pedidos_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.pedidos_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')

        # Tooltip para observações
        self.tooltip = ModernTooltip(self.pedidos_tree)
        self.pedidos_tree.bind("<Motion>", self.mostrar_tooltip)
        self.pedidos_tree.bind("<Leave>", lambda e: self.tooltip.hidetip())

        # Controles
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=5)

        acoes = [
            ("✅ Pronto", self.marcar_como_pronto, "Marcar pedido como pronto"),
            ("📩 Notificar", self.notificar_cliente, "Enviar notificação ao cliente"),
            ("❌ Cancelar", self.cancelar_pedido, "Cancelar pedido selecionado"),
            ("📝 Detalhes", self.mostrar_detalhes_pedido, "Mostrar detalhes do pedido")
        ]

        for texto, comando, tooltip_text in acoes:
            btn = ttk.Button(btn_frame, text=texto, command=comando)
            btn.pack(side='left', padx=5)
            self.create_tooltip(btn, tooltip_text)

    def setup_aba_historico(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📜 Histórico")

        self.historico_text = tk.Text(frame, wrap=tk.WORD, state='disabled',
                                      font=('Segoe UI', 10), padx=10, pady=10,
                                      bg=COR_TERCIARIA, fg=COR_TEXTO)

        scroll_y = ttk.Scrollbar(frame, command=self.historico_text.yview)
        scroll_x = ttk.Scrollbar(frame, command=self.historico_text.xview, orient='horizontal')
        self.historico_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.historico_text.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(btn_frame, text="🗑️ Limpar", command=self.limpar_historico).pack(side='left')
        ttk.Button(btn_frame, text="💾 Salvar", command=self.salvar_historico).pack(side='left', padx=5)

    def setup_aba_ferramentas(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🛠️ Ferramentas")

        ferramentas = [
            ("📤 Exportar Dados", self.exportar_dados, "Exportar dados para arquivo"),
            ("📊 Estatísticas", self.mostrar_estatisticas, "Mostrar estatísticas detalhadas"),
            ("🔔 Notificar Todos", self.notificar_todos, "Enviar mensagem para todos os clientes"),
            ("⏰ Horário Marmita", self.verificar_horario_marmita, "Verificar horário para marmitas"),
            ("📅 Relatório Diário", self.gerar_relatorio_diario, "Gerar relatório de vendas diário"),
            ("📈 Gráficos", self.mostrar_graficos, "Mostrar gráficos de vendas")
        ]

        for i, (texto, comando, tooltip) in enumerate(ferramentas):
            btn = ttk.Button(frame, text=texto, command=comando)
            btn.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky='nsew')
            self.create_tooltip(btn, tooltip)

        for i in range(2):
            frame.grid_columnconfigure(i, weight=1)
        for i in range((len(ferramentas) + 1) // 2):
            frame.grid_rowconfigure(i, weight=1)

    def setup_aba_cardapio(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🍽️ Cardápio")

        # Frame para cardápio normal
        cardapio_frame = ttk.LabelFrame(frame, text="Cardápio Regular")
        cardapio_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.cardapio_tree = ttk.Treeview(cardapio_frame, columns=('Item', 'Preço'), show='headings')
        self.cardapio_tree.heading('Item', text='Item')
        self.cardapio_tree.heading('Preço', text='Preço (R$)')
        self.cardapio_tree.column('Item', width=300)
        self.cardapio_tree.column('Preço', width=100, anchor='center')

        scroll_y = ttk.Scrollbar(cardapio_frame, command=self.cardapio_tree.yview)
        scroll_x = ttk.Scrollbar(cardapio_frame, command=self.cardapio_tree.xview, orient='horizontal')
        self.cardapio_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.cardapio_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')

        # Frame para cardápio do dia (marmita)
        marmita_frame = ttk.LabelFrame(frame, text="Marmita do Dia")
        marmita_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.marmita_text = tk.Text(marmita_frame, wrap=tk.WORD, height=5,
                                    font=('Segoe UI', 10), padx=5, pady=5)
        scroll = ttk.Scrollbar(marmita_frame, command=self.marmita_text.yview)
        self.marmita_text.configure(yscrollcommand=scroll.set)

        self.marmita_text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Controles
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(btn_frame, text="🔄 Atualizar",
                   command=lambda: self.executar_tarefa(self.atualizar_cardapio)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="✏️ Editar Cardápio",
                   command=self.editar_cardapio).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🍱 Editar Marmita",
                   command=self.editar_marmita).pack(side='left', padx=5)

    def setup_aba_configuracoes(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="⚙️ Configurações")

        # Frame para configurações gerais
        geral_frame = ttk.LabelFrame(frame, text="Configurações Gerais")
        geral_frame.pack(fill='x', padx=10, pady=5)

        # Configurações de horário da marmita
        ttk.Label(geral_frame, text="Horário para pedidos de marmita:").grid(row=0, column=0, padx=10, pady=5,
                                                                             sticky='w')

        self.hora_inicio = ttk.Entry(geral_frame, width=5)
        self.hora_inicio.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(geral_frame, text="às").grid(row=0, column=2, padx=5, pady=5)
        self.hora_fim = ttk.Entry(geral_frame, width=5)
        self.hora_fim.grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(geral_frame, text="💾 Salvar", command=self.salvar_horario_marmita).grid(row=0, column=4, padx=10,
                                                                                           pady=5)

        # Configurações de atualização
        ttk.Label(geral_frame, text="Intervalo de atualização (segundos):").grid(row=1, column=0, padx=10, pady=5,
                                                                                 sticky='w')
        self.intervalo_atualizacao = ttk.Spinbox(geral_frame, from_=5, to=60, width=5)
        self.intervalo_atualizacao.set(TEMPO_ATUALIZACAO)
        self.intervalo_atualizacao.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(geral_frame, text="💾 Aplicar", command=self.definir_intervalo_atualizacao).grid(row=1, column=2,
                                                                                                   padx=10, pady=5)

        # Frame para configurações de API
        api_frame = ttk.LabelFrame(frame, text="Configurações da API")
        api_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(api_frame, text="URL da API:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.api_url_entry = ttk.Entry(api_frame, width=40)
        self.api_url_entry.insert(0, API_BASE)
        self.api_url_entry.grid(row=0, column=1, padx=5, pady=5, columnspan=2, sticky='we')
        ttk.Button(api_frame, text="💾 Salvar", command=self.salvar_config_api).grid(row=0, column=3, padx=10, pady=5)

        ttk.Label(api_frame, text="Token Telegram:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.telegram_token_entry = ttk.Entry(api_frame, width=40, show="*")
        self.telegram_token_entry.insert(0, TELEGRAM_TOKEN)
        self.telegram_token_entry.grid(row=1, column=1, padx=5, pady=5, columnspan=2, sticky='we')
        ttk.Button(api_frame, text="👁️", width=3, command=self.toggle_token_visibility).grid(row=1, column=3, padx=5,
                                                                                             pady=5)

        # Frame para tema
        tema_frame = ttk.LabelFrame(frame, text="Aparência")
        tema_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(tema_frame, text="Tema:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.tema_var = tk.StringVar(value="claro")
        ttk.Radiobutton(tema_frame, text="Claro", variable=self.tema_var,
                        value="claro", command=self.aplicar_tema).grid(row=0, column=1, padx=5, pady=5)
        ttk.Radiobutton(tema_frame, text="Escuro", variable=self.tema_var,
                        value="escuro", command=self.aplicar_tema).grid(row=0, column=2, padx=5, pady=5)
        ttk.Radiobutton(tema_frame, text="Sistema", variable=self.tema_var,
                        value="sistema", command=self.aplicar_tema).grid(row=0, column=3, padx=5, pady=5)

    def setup_aba_dashboard(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📊 Dashboard")

        # Frame para métricas rápidas
        metrics_frame = ttk.Frame(frame)
        metrics_frame.pack(fill='x', padx=10, pady=10)

        self.metric_widgets = {
            'total_pedidos': self.create_metric_card(metrics_frame, "Total Pedidos", "0", 0),
            'pedidos_hoje': self.create_metric_card(metrics_frame, "Pedidos Hoje", "0", 1),
            'receita_total': self.create_metric_card(metrics_frame, "Receita Total", "R$ 0.00", 2),
            'receita_hoje': self.create_metric_card(metrics_frame, "Receita Hoje", "R$ 0.00", 3)
        }

        # Frame para gráficos
        graph_frame = ttk.Frame(frame)
        graph_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.canvas = None
        self.setup_dashboard_graphs(graph_frame)

    def create_metric_card(self, parent, title, value, column):
        card = ttk.Frame(parent, relief='solid', borderwidth=1)
        card.grid(row=0, column=column, padx=5, pady=5, sticky='nsew')

        title_label = ttk.Label(card, text=title, font=('Segoe UI', 9, 'bold'))
        title_label.pack(pady=(5, 0))

        value_label = ttk.Label(card, text=value, font=('Segoe UI', 14))
        value_label.pack(pady=(0, 5))

        parent.columnconfigure(column, weight=1)
        return value_label

    def setup_dashboard_graphs(self, parent):
        # Destruir o canvas anterior se existir
        if hasattr(self, 'canvas') and self.canvas is not None:
            self.canvas.get_tk_widget().destroy()

        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            fig.subplots_adjust(hspace=0.5)

            # Gráfico de status de pedidos
            status_count = {'Recebido': 0, 'Preparando': 0, 'Pronto': 0, 'Entregue': 0, 'Cancelado': 0}
            for pedido in self.pedidos:
                status_count[pedido.status] += 1

            ax1.bar(status_count.keys(), status_count.values(),
                    color=['#3498db', '#f39c12', '#2ecc71', '#95a5a6', '#e74c3c'])
            ax1.set_title('Status dos Pedidos')
            ax1.set_ylabel('Quantidade')

            # Gráfico de pedidos por hora (simulado)
            hours = [f"{h}:00" for h in range(8, 18)]
            orders = [max(0, min(15, int(10 + 5 * (h - 12) ** 2 / 16))) for h in range(8, 18)]
            ax2.plot(hours, orders, marker='o', color=COR_SECUNDARIA)
            ax2.set_title('Pedidos por Hora')
            ax2.set_ylabel('Quantidade')
            ax2.grid(True, linestyle='--', alpha=0.6)

            # Criar novo canvas
            self.canvas = FigureCanvasTkAgg(fig, master=parent)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar gráficos: {str(e)}")
            self.log(f"Erro ao gerar gráficos: {str(e)}", error=True)

    def carregar_estilos(self):
        style = ttk.Style()

        # Configuração do tema geral
        style.theme_use('default')

        # Estilo padrão
        style.configure('.',
                        font=('Segoe UI', 10),
                        background=COR_FUNDO,
                        foreground=COR_TEXTO,
                        fieldbackground=COR_FUNDO)

        # Configurações específicas
        style.configure('TFrame', background=COR_FUNDO)
        style.configure('TLabel',
                        background=COR_FUNDO,
                        foreground=COR_TEXTO,
                        font=('Segoe UI', 10))
        style.configure('TButton',
                        background=COR_BOTAO,
                        foreground=COR_TEXTO_ESCURO,
                        font=('Segoe UI', 10, 'bold'),
                        borderwidth=1)
        style.map('TButton',
                  background=[('active', COR_SECUNDARIA), ('pressed', COR_PRIMARIA)])

        style.configure('TEntry',
                        fieldbackground='white',
                        foreground=COR_TEXTO)
        style.configure('TCombobox',
                        fieldbackground='white',
                        foreground=COR_TEXTO)

        # Notebook (abas)
        style.configure('TNotebook', background=COR_FUNDO)
        style.configure('TNotebook.Tab',
                        padding=[10, 5],
                        background=COR_TERCIARIA,
                        foreground=COR_TEXTO)
        style.map('TNotebook.Tab',
                  background=[('selected', COR_FUNDO)],
                  foreground=[('selected', COR_PRIMARIA)])

        # Treeview (tabelas)
        style.configure("Treeview",
                        background='white',
                        foreground=COR_TEXTO,
                        rowheight=25,
                        fieldbackground='white',
                        bordercolor=COR_BORDA,
                        lightcolor=COR_BORDA,
                        darkcolor=COR_BORDA)
        style.configure("Treeview.Heading",
                        background=COR_PRIMARIA,
                        foreground='white',
                        font=('Segoe UI', 10, 'bold'))
        style.map('Treeview',
                  background=[('selected', COR_SECUNDARIA)],
                  foreground=[('selected', 'white')])

        # Barra de status
        style.configure("Status.TLabel",
                        background=COR_PRIMARIA,
                        foreground='white',
                        padding=5,
                        font=('Segoe UI', 9))

        self.status_bar.configure(style="Status.TLabel")

        # Aplicar tema inicial
        self.aplicar_tema()

    def aplicar_tema(self):
        tema = self.tema_var.get()

        if tema == "escuro":
            self.root.tk_setPalette(
                background='#2d2d2d',
                foreground='#ffffff',
                activeBackground='#3d3d3d',
                activeForeground='#ffffff'
            )
        elif tema == "claro":
            self.root.tk_setPalette(
                background=COR_FUNDO,
                foreground=COR_TEXTO,
                activeBackground=COR_SECUNDARIA,
                activeForeground='white'
            )
        else:  # sistema
            self.root.tk_setPalette(background='', foreground='', activeBackground='', activeForeground='')

    def toggle_token_visibility(self):
        current_show = self.telegram_token_entry.cget('show')
        self.telegram_token_entry.config(show='' if current_show else '*')

    def salvar_config_api(self):
        global API_BASE, TELEGRAM_TOKEN
        API_BASE = self.api_url_entry.get()
        TELEGRAM_TOKEN = self.telegram_token_entry.get()
        messagebox.showinfo("Sucesso", "Configurações da API atualizadas!")
        self.log("Configurações da API atualizadas")

    def iniciar_thread_atualizacao(self):
        self.thread_ativo = True
        self.thread = Thread(target=self.thread_atualizacao, daemon=True)
        self.thread.start()

    def thread_atualizacao(self):
        while self.thread_ativo:
            self.executar_tarefa(self.atualizar_tudo)
            time_module.sleep(TEMPO_ATUALIZACAO)

    def executar_tarefa(self, tarefa, *args):
        self.fila_tarefas.put((tarefa, args))
        self.root.event_generate("<<TarefaConcluida>>", when="tail")

    def verificar_tarefas_pendentes(self):
        try:
            while True:
                tarefa, args = self.fila_tarefas.get_nowait()
                try:
                    self.show_progress(True)
                    tarefa(*args)
                except Exception as e:
                    self.log(f"Erro na tarefa: {str(e)}", error=True)
                finally:
                    self.show_progress(False)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.verificar_tarefas_pendentes)

    def show_progress(self, show):
        if show:
            self.progress.pack(fill='x', pady=2)
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def atualizar_tudo(self):
        self.atualizar_pedidos()
        self.atualizar_cardapio()
        self.atualizar_dashboard()
        self.atualizar_status("Sistema atualizado em " + datetime.now().strftime("%H:%M:%S"))

    def atualizar_pedidos(self):
        try:
            response = requests.get(f"{API_BASE}/pedidos", timeout=5)
            response.raise_for_status()
            novos_pedidos = [
                Pedido(
                    id=p.get('id'),
                    usuario=p.get('usuario'),
                    item=p.get('item'),
                    observacoes=p.get('observacoes', 'Nenhuma'),
                    status=p.get('status', 'Recebido'),
                    timestamp=p.get('timestamp', ''),
                    user_id=p.get('user_id')
                ) for p in response.json()
            ]

            if novos_pedidos != self.pedidos:
                self.pedidos = novos_pedidos
                self.atualizar_treeview_pedidos()
                self.log("Lista de pedidos atualizada")

        except requests.exceptions.RequestException as e:
            self.atualizar_status(f"Erro de conexão: {str(e)}")
            self.log(f"Erro ao conectar ao servidor: {str(e)}", error=True)
        except Exception as e:
            self.log(f"Erro ao atualizar pedidos: {str(e)}", error=True)

    def atualizar_treeview_pedidos(self):
        self.pedidos_tree.delete(*self.pedidos_tree.get_children())

        status_cores = {
            'Recebido': 'black',
            'Preparando': 'blue',
            'Pronto': 'green',
            'Entregue': 'gray',
            'Cancelado': 'red'
        }

        for pedido in self.pedidos:
            hora_formatada = pedido.timestamp[:16].replace('T', ' ') if pedido.timestamp else ''
            self.pedidos_tree.insert('', 'end', values=(
                pedido.id,
                pedido.usuario,
                pedido.item,
                pedido.status,
                hora_formatada
            ), tags=(pedido.status,))

        for status, cor in status_cores.items():
            self.pedidos_tree.tag_configure(status, foreground=cor)

        self.aplicar_filtros()

    def atualizar_cardapio(self):
        try:
            # Cardápio normal
            response = requests.get(f"{API_BASE}/cardapio", timeout=5)
            response.raise_for_status()
            self.cardapio = [
                ItemCardapio(nome=item.get('nome'), preco=float(item.get('preco', 0)))
                for item in response.json()
            ]

            # Cardápio do dia (marmita)
            response = requests.get(f"{API_BASE}/cardapio-do-dia", timeout=5)
            response.raise_for_status()
            data = response.json()
            self.cardapio_do_dia = data.get('marmita', []) if isinstance(data, dict) else []

            self.marmita_text.config(state='normal')
            self.marmita_text.delete('1.0', 'end')
            self.marmita_text.insert('1.0', "\n".join(self.cardapio_do_dia))
            self.marmita_text.config(state='disabled')

            self.atualizar_treeview_cardapio()
            self.log("Cardápio atualizado")

        except requests.exceptions.RequestException as e:
            self.atualizar_status(f"Erro ao carregar cardápio: {str(e)}")
            self.log(f"Erro ao carregar cardápio: {str(e)}", error=True)
        except Exception as e:
            self.log(f"Erro ao processar cardápio: {str(e)}", error=True)

    def atualizar_treeview_cardapio(self):
        self.cardapio_tree.delete(*self.cardapio_tree.get_children())
        for item in self.cardapio:
            self.cardapio_tree.insert('', 'end', values=(item.nome, f"R$ {item.preco:.2f}"))

    def atualizar_dashboard(self):
        # Atualizar métricas
        total_pedidos = len(self.pedidos)
        pedidos_hoje = len([p for p in self.pedidos if p.timestamp.startswith(datetime.now().strftime("%Y-%m-%d"))])

        # Simular receita (em uma aplicação real, isso viria da API)
        receita_total = sum(15.0 for _ in self.pedidos)  # Valor fixo simulado
        receita_hoje = sum(15.0 for p in self.pedidos if p.timestamp.startswith(datetime.now().strftime("%Y-%m-%d")))

        self.metric_widgets['total_pedidos'].config(text=str(total_pedidos))
        self.metric_widgets['pedidos_hoje'].config(text=str(pedidos_hoje))
        self.metric_widgets['receita_total'].config(text=f"R$ {receita_total:.2f}")
        self.metric_widgets['receita_hoje'].config(text=f"R$ {receita_hoje:.2f}")

        # Atualizar gráficos
        self.setup_dashboard_graphs(self.notebook.winfo_children()[-1])  # Pega o frame do dashboard

    def aplicar_filtros(self):
        filtro_texto = self.filtro_entry.get().lower()
        filtro_status = self.status_filter.get()

        for child in self.pedidos_tree.get_children():
            valores = self.pedidos_tree.item(child)['values']
            texto_match = any(filtro_texto in str(v).lower() for v in valores)
            status_match = (filtro_status == "Todos" or valores[3] == filtro_status)
            self.pedidos_tree.item(child, tags=('visible' if texto_match and status_match else 'hidden'))

        self.pedidos_tree.tag_configure('hidden', foreground='gray90')

    def mostrar_tooltip(self, event):
        region = self.pedidos_tree.identify("region", event.x, event.y)
        if region == "cell":
            item = self.pedidos_tree.identify_row(event.y)
            if item:
                pedido_id = self.pedidos_tree.item(item, 'values')[0]
                pedido = next((p for p in self.pedidos if p.id == pedido_id), None)
                if pedido and pedido.observacoes:
                    self.tooltip.showtip(f"Observações:\n{pedido.observacoes}")
                else:
                    self.tooltip.hidetip()

    def obter_pedido_selecionado(self) -> Optional[Pedido]:
        selecao = self.pedidos_tree.selection()
        if not selecao:
            messagebox.showwarning("Aviso", "Selecione um pedido primeiro")
            return None

        pedido_id = self.pedidos_tree.item(selecao[0], 'values')[0]
        return next((p for p in self.pedidos if p.id == pedido_id), None)

    def mostrar_detalhes_pedido(self):
        pedido = self.obter_pedido_selecionado()
        if not pedido:
            return

        detalhes = f"""
        📋 Detalhes do Pedido #{pedido.id}

        👤 Cliente: {pedido.usuario}
        🍽️ Item: {pedido.item}
        📝 Observações: {pedido.observacoes or 'Nenhuma'}
        📊 Status: {pedido.status}
        ⏰ Data/Hora: {pedido.timestamp.replace('T', ' ')[:16]}
        """

        messagebox.showinfo(f"Pedido #{pedido.id}", detalhes.strip())

    def marcar_como_pronto(self):
        pedido = self.obter_pedido_selecionado()
        if not pedido:
            return

        if messagebox.askyesno("Confirmar", f"Marcar pedido #{pedido.id} como pronto?"):
            self.executar_tarefa(self._marcar_como_pronto, pedido)

    def _marcar_como_pronto(self, pedido: Pedido):
        try:
            response = requests.patch(
                f"{API_BASE}/pedidos/{pedido.id}",
                json={'status': 'Pronto'},
                timeout=5
            )
            response.raise_for_status()

            self.log(f"Pedido #{pedido.id} marcado como pronto")
            self.enviar_notificacao_telegram(pedido, "✅ Seu pedido está pronto para retirada!")
            self.atualizar_pedidos()

        except requests.exceptions.RequestException as e:
            self.log(f"Erro ao atualizar pedido: {str(e)}", error=True)
            messagebox.showerror("Erro", "Falha ao atualizar pedido")

    def cancelar_pedido(self):
        pedido = self.obter_pedido_selecionado()
        if not pedido:
            return

        if messagebox.askyesno("Confirmar", f"Cancelar o pedido #{pedido.id}?"):
            self.executar_tarefa(self._cancelar_pedido, pedido)

    def _cancelar_pedido(self, pedido: Pedido):
        try:
            response = requests.patch(
                f"{API_BASE}/pedidos/{pedido.id}",
                json={'status': 'Cancelado'},
                timeout=5
            )
            response.raise_for_status()

            self.log(f"Pedido #{pedido.id} cancelado")
            self.enviar_notificacao_telegram(pedido, "❌ Seu pedido foi cancelado")
            self.atualizar_pedidos()

        except requests.exceptions.RequestException as e:
            self.log(f"Erro ao cancelar pedido: {str(e)}", error=True)
            messagebox.showerror("Erro", "Falha ao cancelar pedido")

    def notificar_cliente(self):
        pedido = self.obter_pedido_selecionado()
        if not pedido:
            return

        mensagem = simpledialog.askstring(
            "Notificar Cliente",
            f"Digite a mensagem para {pedido.usuario}:",
            parent=self.root
        )

        if mensagem:
            self.executar_tarefa(self._notificar_cliente, pedido, mensagem)

    def _notificar_cliente(self, pedido: Pedido, mensagem: str):
        try:
            self.enviar_notificacao_telegram(pedido, mensagem)
            self.log(f"Notificação enviada para {pedido.usuario}")
            messagebox.showinfo("Sucesso", "Notificação enviada com sucesso")

        except Exception as e:
            self.log(f"Erro ao notificar cliente: {str(e)}", error=True)
            messagebox.showerror("Erro", "Falha ao enviar notificação")

    def notificar_todos(self):
        if messagebox.askyesno("Confirmar", "Enviar notificação para todos os clientes?"):
            mensagem = simpledialog.askstring(
                "Notificar Todos",
                "Digite a mensagem para todos os clientes:",
                parent=self.root
            )

            if mensagem:
                self.executar_tarefa(self._notificar_todos, mensagem)

    def _notificar_todos(self, mensagem: str):
        try:
            participantes = requests.get(f"{API_BASE}/participantes", timeout=5).json()
            total = 0

            for p in participantes:
                if p.get('telegram_id'):
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                'chat_id': p['telegram_id'],
                                'text': f"📢 Mensagem da Cantina:\n{mensagem}",
                                'parse_mode': 'Markdown'
                            },
                            timeout=5
                        )
                        total += 1
                    except Exception as e:
                        self.log(f"Erro ao notificar {p.get('nome')}: {str(e)}", error=True)

            messagebox.showinfo("Concluído", f"Notificações enviadas para {total} usuários")

        except Exception as e:
            self.log(f"Erro ao notificar todos: {str(e)}", error=True)
            messagebox.showerror("Erro", "Falha ao enviar notificações")

    def enviar_notificacao_telegram(self, pedido: Pedido, mensagem: str):
        if not pedido.user_id:
            return

        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    'chat_id': pedido.user_id,
                    'text': f"🔔 *Atualização do Pedido* #{pedido.id}\n\n{mensagem}",
                    'parse_mode': 'Markdown'
                },
                timeout=5
            )
        except Exception as e:
            self.log(f"Erro ao enviar notificação Telegram: {str(e)}", error=True)

    def editar_cardapio(self):
        editor = Toplevel(self.root)
        editor.title("✏️ Editar Cardápio")
        editor.geometry("700x500")
        editor.resizable(True, True)

        # Aplicar tema consistente
        editor.tk_setPalette(background=COR_FUNDO)
        style = ttk.Style()
        style.configure('TFrame', background=COR_FUNDO)
        style.configure('TLabel', background=COR_FUNDO, foreground=COR_TEXTO, font=('Segoe UI', 10))
        style.configure('TButton', background=COR_BOTAO, foreground=COR_TEXTO_ESCURO, font=('Segoe UI', 10))
        style.configure('Header.TLabel', font=('Segoe UI', 11, 'bold'), foreground=COR_PRIMARIA)

        # Frame principal
        main_frame = ttk.Frame(editor, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Cabeçalho com instruções
        ttk.Label(
            main_frame,
            text="Formato: Nome do Item - Preço (Ex: Prato Feito - 15.50)",
            style='Header.TLabel'
        ).pack(pady=(0, 10))

        # Frame de texto com borda
        text_frame = ttk.Frame(main_frame, relief='solid', borderwidth=1)
        text_frame.pack(fill='both', expand=True)

        # Widget de texto com estilo
        texto = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),  # Fonte monoespaçada para alinhamento
            bg='white',
            fg=COR_TEXTO,
            insertbackground=COR_TEXTO,
            selectbackground=COR_SECUNDARIA,
            selectforeground='white',
            padx=10,
            pady=10
        )

        # Scrollbars
        scroll_y = ttk.Scrollbar(text_frame, orient='vertical', command=texto.yview)
        scroll_x = ttk.Scrollbar(text_frame, orient='horizontal', command=texto.xview)
        texto.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # Layout do texto e scrollbars
        texto.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')

        # Configurar expansão
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        # Carregar dados atuais com tratamento robusto
        try:
            cardapio_formatado = []
            for item in self.cardapio:
                # Formatar cada item como "Nome - Preço"
                nome = item.nome.strip()
                preco = f"{float(item.preco):.2f}".replace('.', ',')
                cardapio_formatado.append(f"{nome} - {preco}")

            texto.insert('1.0', '\n'.join(cardapio_formatado))
        except Exception as e:
            self.log(f"Erro ao carregar cardápio: {str(e)}", error=True)
            texto.insert('1.0', "")

        # Frame de botões
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        def salvar():
            try:
                conteudo = texto.get('1.0', 'end-1c')
                novos_itens = []
                erros = []

                for i, linha in enumerate(conteudo.split('\n'), 1):
                    linha = linha.strip()
                    if not linha:
                        continue

                    # Processar cada linha com regex melhorado
                    match = re.match(r'^(.+?)\s*-\s*([Rr$]?\s*[\d,]+\.?\d*)\s*$', linha)
                    if not match:
                        erros.append(f"Linha {i}: Formato inválido - '{linha}'")
                        continue

                    nome = match.group(1).strip()
                    preco_str = match.group(2).replace('R$', '').replace('r$', '').replace(' ', '').strip()

                    try:
                        # Converter preço para float (aceita . ou , como separador)
                        preco = float(preco_str.replace(',', '.'))
                        if preco < 0:
                            raise ValueError("Preço não pode ser negativo")
                        novos_itens.append({'nome': nome, 'preco': preco})
                    except ValueError:
                        erros.append(f"Linha {i}: Preço inválido - '{preco_str}'")

                if erros:
                    raise ValueError("\n".join(erros))

                if not novos_itens:
                    raise ValueError("O cardápio não pode estar vazio")

                # DEBUG: Mostrar o JSON que será enviado
                print("Enviando para a API:", json.dumps(novos_itens, indent=2))

                # Enviar para API com headers corretos
                headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }

                response = requests.post(
                    f"{API_BASE}/cardapio",
                    json=novos_itens,  # Usando o parâmetro json que automaticamente serializa
                    headers=headers,
                    timeout=10
                )

                # Verificar se a resposta foi bem sucedida
                if response.status_code == 400:
                    # Se for Bad Request, tentar entender o erro
                    try:
                        erro_api = response.json()
                        raise ValueError(f"API retornou erro:\n{erro_api.get('message', str(erro_api))}")
                    except:
                        raise ValueError(f"API retornou Bad Request: {response.text}")

                response.raise_for_status()  # Lança exceção para outros códigos de erro

                # Atualizar localmente
                self.atualizar_cardapio()

                # Feedback visual
                messagebox.showinfo(
                    "Sucesso",
                    "Cardápio atualizado com sucesso!",
                    parent=editor
                )
                editor.destroy()

            except requests.exceptions.RequestException as e:
                self.log(f"Erro de conexão ao salvar cardápio: {str(e)}", error=True)
                messagebox.showerror(
                    "Erro de Conexão",
                    f"Não foi possível conectar ao servidor:\n{str(e)}",
                    parent=editor
                )
            except ValueError as e:
                messagebox.showwarning(
                    "Erro de Validação",
                    f"Corrija os seguintes erros:\n\n{str(e)}",
                    parent=editor
                )
            except Exception as e:
                self.log(f"Erro inesperado ao salvar cardápio: {str(e)}", error=True)
                messagebox.showerror(
                    "Erro",
                    f"Ocorreu um erro inesperado:\n{str(e)}",
                    parent=editor
                )

        # Botões com ícones e tooltips
        btn_cancelar = ttk.Button(
            btn_frame,
            text="❌ Cancelar",
            command=editor.destroy,
            style='TButton'
        )
        btn_cancelar.pack(side='left', padx=5)
        self.create_tooltip(btn_cancelar, "Descartar alterações e fechar")

        btn_salvar = ttk.Button(
            btn_frame,
            text="💾 Salvar Cardápio",
            command=salvar,
            style='TButton'
        )
        btn_salvar.pack(side='right', padx=5)
        self.create_tooltip(btn_salvar, "Salvar alterações no cardápio")

        # Botão auxiliar para formatação
        btn_formatar = ttk.Button(
            btn_frame,
            text="🔧 Formatar",
            command=lambda: self.auto_formatar_cardapio(texto),
            style='TButton'
        )
        btn_formatar.pack(side='right', padx=5)
        self.create_tooltip(btn_formatar, "Formatar automaticamente o cardápio")

        # Focar no campo de texto
        texto.focus_set()

    def auto_formatar_cardapio(self, text_widget):
        """Função auxiliar para formatar automaticamente o cardápio"""
        try:
            conteudo = text_widget.get('1.0', 'end-1c')
            linhas_formatadas = []

            for linha in conteudo.split('\n'):
                linha = linha.strip()
                if not linha:
                    continue

                # Adiciona tratamento inteligente de formatação
                if '-' not in linha:
                    # Se não tem hífen, assume que é só nome (preço zero)
                    linhas_formatadas.append(f"{linha} - 0,00")
                else:
                    # Formata linhas que já tem hífen
                    partes = linha.split('-', 1)
                    nome = partes[0].strip()
                    preco = partes[1].strip()

                    # Padroniza o preço
                    try:
                        preco_float = float(preco.replace(',', '.'))
                        preco_formatado = f"{preco_float:.2f}".replace('.', ',')
                        linhas_formatadas.append(f"{nome} - {preco_formatado}")
                    except ValueError:
                        linhas_formatadas.append(f"{nome} - 0,00")

            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', '\n'.join(linhas_formatadas))

        except Exception as e:
            self.log(f"Erro ao formatar cardápio: {str(e)}", error=True)

    def editar_marmita(self):
        editor = Toplevel(self.root)
        editor.title("✏️ Editar Marmita do Dia")
        editor.geometry("500x800")
        editor.resizable(True, True)

        # Aplicar estilo consistente
        editor.tk_setPalette(background=COR_FUNDO)
        style = ttk.Style()
        style.configure('TFrame', background=COR_FUNDO)
        style.configure('TLabel', background=COR_FUNDO, foreground=COR_TEXTO)
        style.configure('TButton', background=COR_BOTAO, foreground=COR_TEXTO_ESCURO)

        # Frame principal com padding
        main_frame = ttk.Frame(editor, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Label de instrução com estilo
        lbl_instrucao = ttk.Label(
            main_frame,
            text="Digite os itens da marmita (um por linha):",
            font=('Segoe UI', 10, 'bold'),
            foreground=COR_PRIMARIA
        )
        lbl_instrucao.pack(pady=(0, 10))

        # Frame para o texto com borda e estilo
        text_frame = ttk.Frame(main_frame, relief='solid', borderwidth=1)
        text_frame.pack(fill='both', expand=True)

        # Widget de texto com estilo
        texto = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg='white',
            fg=COR_TEXTO,
            insertbackground=COR_TEXTO,
            selectbackground=COR_SECUNDARIA,
            selectforeground='white',
            padx=5,
            pady=5
        )

        # Scrollbars com estilo
        scroll_y = ttk.Scrollbar(text_frame, orient='vertical', command=texto.yview)
        scroll_x = ttk.Scrollbar(text_frame, orient='horizontal', command=texto.xview)
        texto.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # Layout
        texto.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')

        # Configurar expansão
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        # Carregar dados atuais com tratamento robusto
        try:
            if isinstance(self.cardapio_do_dia, str):
                # Remove espaços extras e linhas vazias
                conteudo = '\n'.join(line.strip() for line in self.cardapio_do_dia.split('\n') if line.strip())
                texto.insert('1.0', conteudo)
            elif isinstance(self.cardapio_do_dia, list):
                # Filtra itens válidos e remove espaços extras
                conteudo = '\n'.join(str(item).strip() for item in self.cardapio_do_dia if str(item).strip())
                texto.insert('1.0', conteudo)
            else:
                texto.insert('1.0', "")
        except Exception as e:
            self.log(f"Erro ao carregar marmita: {str(e)}", error=True)
            texto.insert('1.0', "")

        # Frame para os botões com estilo
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        def salvar():
            try:
                # Obter conteúdo e formatar corretamente
                conteudo = texto.get('1.0', 'end-1c')

                # Processamento robusto:
                # 1. Divide por linhas
                # 2. Remove espaços extras
                # 3. Filtra linhas vazias
                # 4. Remove duplicatas
                linhas = [line.strip() for line in conteudo.split('\n')]
                itens_marmita = []
                seen = set()

                for item in linhas:
                    if item and item not in seen:
                        itens_marmita.append(item)
                        seen.add(item)

                if not itens_marmita:
                    raise ValueError("A marmita não pode estar vazia")

                # Enviar para a API
                response = requests.post(
                    f"{API_BASE}/cardapio-do-dia",
                    json={'marmita': itens_marmita},
                    timeout=5
                )
                response.raise_for_status()

                # Atualizar localmente
                self.cardapio_do_dia = itens_marmita
                self.atualizar_cardapio()

                # Feedback visual
                messagebox.showinfo("Sucesso", "Marmita atualizada com sucesso!", parent=editor)
                editor.destroy()

            except requests.exceptions.RequestException as e:
                self.log(f"Erro de conexão: {str(e)}", error=True)
                messagebox.showerror(
                    "Erro de Conexão",
                    f"Não foi possível conectar ao servidor:\n{str(e)}",
                    parent=editor
                )
            except ValueError as e:
                messagebox.showwarning(
                    "Aviso",
                    str(e),
                    parent=editor
                )
            except Exception as e:
                self.log(f"Erro ao salvar marmita: {str(e)}", error=True)
                messagebox.showerror(
                    "Erro",
                    f"Ocorreu um erro inesperado:\n{str(e)}",
                    parent=editor
                )

        # Botões com estilo e tooltips
        btn_cancelar = ttk.Button(
            btn_frame,
            text="❌ Cancelar",
            command=editor.destroy,
            style='TButton'
        )
        btn_cancelar.pack(side='left', padx=5)
        self.create_tooltip(btn_cancelar, "Cancelar edição sem salvar")

        btn_salvar = ttk.Button(
            btn_frame,
            text="💾 Salvar",
            command=salvar,
            style='TButton'
        )
        btn_salvar.pack(side='right', padx=5)
        self.create_tooltip(btn_salvar, "Salvar alterações na marmita")

        # Focar no campo de texto ao abrir
        texto.focus_set()

    def verificar_horario_marmita(self):
        agora = datetime.now().time()
        if HORARIO_MARMITA_INICIO <= agora <= HORARIO_MARMITA_FIM:
            message = "✅ Pedidos de marmita estão liberados"
            icon = "info"
        else:
            message = "❌ Fora do horário para pedidos de marmita"
            icon = "warning"

        messagebox.showinfo(
            "⏰ Horário Marmita",
            f"{message}\n\nHorário permitido: {HORARIO_MARMITA_INICIO.strftime('%H:%M')} "
            f"às {HORARIO_MARMITA_FIM.strftime('%H:%M')}"
        )

    def salvar_horario_marmita(self):
        try:
            global HORARIO_MARMITA_INICIO, HORARIO_MARMITA_FIM

            inicio = time.fromisoformat(self.hora_inicio.get())
            fim = time.fromisoformat(self.hora_fim.get())

            if inicio >= fim:
                raise ValueError("Horário de início deve ser antes do horário de fim")

            HORARIO_MARMITA_INICIO = inicio
            HORARIO_MARMITA_FIM = fim

            messagebox.showinfo("Sucesso", "Horário da marmita atualizado!")
            self.log("Horário da marmita atualizado")

        except Exception as e:
            messagebox.showerror("Erro", f"Horário inválido: {str(e)}")
            self.log(f"Erro ao atualizar horário: {str(e)}", error=True)

    def definir_intervalo_atualizacao(self):
        try:
            global TEMPO_ATUALIZACAO
            TEMPO_ATUALIZACAO = int(self.intervalo_atualizacao.get())
            messagebox.showinfo("Sucesso", f"Intervalo de atualização definido para {TEMPO_ATUALIZACAO} segundos")
            self.log(f"Intervalo de atualização alterado para {TEMPO_ATUALIZACAO} segundos")
        except ValueError:
            messagebox.showerror("Erro", "Digite um número válido")
            self.log("Erro ao definir intervalo de atualização", error=True)

    def exportar_dados(self):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=f"pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump([p.__dict__ for p in self.pedidos], f, indent=4, ensure_ascii=False)

                messagebox.showinfo("Sucesso", f"Dados exportados para:\n{filename}")
                self.log(f"Dados exportados para {filename}")
                return True
            return False
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar: {str(e)}")
            self.log(f"Erro ao exportar dados: {str(e)}", error=True)
            return False

    def salvar_historico(self):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.historico_text.get('1.0', 'end-1c'))

                messagebox.showinfo("Sucesso", f"Histórico salvo em:\n{filename}")
                self.log(f"Histórico salvo em {filename}")
                return True
            return False
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar histórico: {str(e)}")
            self.log(f"Erro ao salvar histórico: {str(e)}", error=True)
            return False

    def mostrar_estatisticas(self):
        status_count = {}
        for pedido in self.pedidos:
            status_count[pedido.status] = status_count.get(pedido.status, 0) + 1

        # Calcular estatísticas adicionais
        hoje = datetime.now().strftime("%Y-%m-%d")
        pedidos_hoje = len([p for p in self.pedidos if p.timestamp.startswith(hoje)])

        # Simular valores monetários (em uma aplicação real, isso viria do banco de dados)
        receita_total = sum(15.0 for _ in self.pedidos)  # Valor fixo simulado
        receita_hoje = sum(15.0 for p in self.pedidos if p.timestamp.startswith(hoje))

        estatisticas = """
        📊 Estatísticas de Pedidos 📊

        📅 Hoje:
        • Pedidos: {pedidos_hoje}
        • Receita: R$ {receita_hoje:.2f}

        🗓️ Total:
        • Pedidos: {total_pedidos}
        • Receita: R$ {receita_total:.2f}

        📌 Status Atuais:
        {status_lines}
        """.format(
            pedidos_hoje=pedidos_hoje,
            receita_hoje=receita_hoje,
            total_pedidos=len(self.pedidos),
            receita_total=receita_total,
            status_lines="\n".join(f"• {status}: {count} pedido(s)"
                                   for status, count in sorted(status_count.items()))
        )

        messagebox.showinfo("📊 Estatísticas", estatisticas.strip())

    def gerar_relatorio_diario(self):
        try:
            hoje = datetime.now().strftime("%Y-%m-%d")
            pedidos_hoje = [p for p in self.pedidos if p.timestamp.startswith(hoje)]

            if not pedidos_hoje:
                messagebox.showinfo("Relatório", "Nenhum pedido registrado hoje")
                return

            # Simular valores (em uma aplicação real, isso viria do banco de dados)
            receita_hoje = sum(15.0 for _ in pedidos_hoje)

            relatorio = f"""
            📅 Relatório Diário - {datetime.now().strftime('%d/%m/%Y')}

            📌 Resumo:
            • Total de pedidos: {len(pedidos_hoje)}
            • Receita total: R$ {receita_hoje:.2f}

            🍽️ Itens mais pedidos:
            {self.calcular_itens_mais_pedidos(pedidos_hoje)}

            ⏰ Horário de pico:
            {self.calcular_horario_pico(pedidos_hoje)}
            """

            # Mostrar relatório e oferecer para exportar
            if messagebox.askyesno("Relatório Diário", relatorio.strip() + "\n\nDeseja exportar este relatório?"):
                self.exportar_relatorio(relatorio)

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar relatório: {str(e)}")
            self.log(f"Erro ao gerar relatório: {str(e)}", error=True)

    def calcular_itens_mais_pedidos(self, pedidos):
        itens = {}
        for p in pedidos:
            itens[p.item] = itens.get(p.item, 0) + 1

        top_itens = sorted(itens.items(), key=lambda x: x[1], reverse=True)[:5]
        return "\n".join(f"• {item}: {qtd}x" for item, qtd in top_itens)

    def calcular_horario_pico(self, pedidos):
        horas = {}
        for p in pedidos:
            hora = p.timestamp[11:13] + ":00"  # Extrai apenas a hora
            horas[hora] = horas.get(hora, 0) + 1

        if not horas:
            return "Dados insuficientes"

        pico = max(horas.items(), key=lambda x: x[1])
        return f"• {pico[0]}h com {pico[1]} pedidos"

    def exportar_relatorio(self, relatorio):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"relatorio_{datetime.now().strftime('%Y%m%d')}.txt"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(relatorio)

                messagebox.showinfo("Sucesso", f"Relatório exportado para:\n{filename}")
                self.log(f"Relatório exportado para {filename}")
                return True
            return False
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar relatório: {str(e)}")
            self.log(f"Erro ao exportar relatório: {str(e)}", error=True)
            return False

    def mostrar_graficos(self):
        graficos_window = Toplevel(self.root)
        graficos_window.title("📈 Gráficos de Vendas")
        graficos_window.geometry("800x600")

        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            fig.subplots_adjust(hspace=0.5)

            # Gráfico 1: Status dos pedidos
            status_count = {'Recebido': 0, 'Preparando': 0, 'Pronto': 0, 'Entregue': 0, 'Cancelado': 0}
            for pedido in self.pedidos:
                status_count[pedido.status] += 1

            ax1.bar(status_count.keys(), status_count.values(),
                    color=['#3498db', '#f39c12', '#2ecc71', '#95a5a6', '#e74c3c'])
            ax1.set_title('Status dos Pedidos')
            ax1.set_ylabel('Quantidade')

            # Gráfico 2: Pedidos por dia (simulado)
            dias = ["Seg", "Ter", "Qua", "Qui", "Sex"]
            pedidos_dia = [12, 15, 8, 20, 25]  # Valores simulados

            ax2.plot(dias, pedidos_dia, marker='o', color=COR_SECUNDARIA)
            ax2.set_title('Pedidos por Dia (Semana Atual)')
            ax2.set_ylabel('Quantidade')
            ax2.grid(True, linestyle='--', alpha=0.6)

            canvas = FigureCanvasTkAgg(fig, master=graficos_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            # Botão para exportar
            btn_frame = ttk.Frame(graficos_window)
            btn_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(btn_frame, text="💾 Exportar Gráficos",
                       command=lambda: self.exportar_graficos(fig)).pack(side='right')

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar gráficos: {str(e)}")
            graficos_window.destroy()
            self.log(f"Erro ao gerar gráficos: {str(e)}", error=True)

    def exportar_graficos(self, fig):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                initialfile=f"graficos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )

            if filename:
                fig.savefig(filename, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Sucesso", f"Gráficos exportados para:\n{filename}")
                self.log(f"Gráficos exportados para {filename}")
                return True
            return False
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar gráficos: {str(e)}")
            self.log(f"Erro ao exportar gráficos: {str(e)}", error=True)
            return False

    def limpar_historico(self):
        if messagebox.askyesno("Confirmar", "Limpar todo o histórico?"):
            self.historico_text.config(state='normal')
            self.historico_text.delete('1.0', 'end')
            self.historico_text.config(state='disabled')
            self.log("Histórico limpo")

    def log(self, mensagem: str, error=False):
        timestamp = datetime.now().strftime('[%H:%M:%S]')
        self.historico_text.config(state='normal')

        if error:
            self.historico_text.tag_config('error', foreground=COR_ERRO)
            self.historico_text.insert('end', f"{timestamp} {mensagem}\n", 'error')
        else:
            self.historico_text.insert('end', f"{timestamp} {mensagem}\n")

        self.historico_text.see('end')
        self.historico_text.config(state='disabled')

    def atualizar_status(self, mensagem: str):
        self.status_bar.config(text=mensagem)

    def fechar_aplicacao(self):
        if messagebox.askokcancel("Sair", "Deseja realmente sair do sistema?"):
            self.thread_ativo = False
            if self.thread.is_alive():
                self.thread.join(timeout=1)
            self.root.destroy()

    def on_window_resize(self, event):
        # Atualizar layouts quando a janela é redimensionada
        if hasattr(self, 'notebook'):
            current_tab = self.notebook.tab(self.notebook.select(), "text")
            if current_tab == "📊 Dashboard":
                self.setup_dashboard_graphs(self.notebook.winfo_children()[-1])

    def create_tooltip(self, widget, text):
        tooltip = ModernTooltip(widget)

        def enter(event):
            tooltip.showtip(text)

        def leave(event):
            tooltip.hidetip()

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def show_help(self):
        help_text = """
        🆘 Ajuda - Painel Administrativo da Cantina

        📋 Pedidos Ativos:
        - Visualize e gerencie os pedidos ativos
        - Clique com o botão direito para opções adicionais

        📜 Histórico:
        - Registro de todas as ações no sistema
        - Pode ser salvo ou limpo conforme necessário

        🛠️ Ferramentas:
        - Exportação de dados
        - Geração de relatórios e estatísticas
        - Envio de notificações em massa

        🍽️ Cardápio:
        - Edição do cardápio regular e da marmita do dia

        ⚙️ Configurações:
        - Ajuste de horários, temas e configurações da API

        📊 Dashboard:
        - Visualização rápida de métricas e gráficos

        ✉️ Suporte:
        Para problemas ou dúvidas, entre em contato com:
        suporte@cantinadigital.com.br
        """

        help_window = Toplevel(self.root)
        help_window.title("❓ Ajuda")
        help_window.geometry("500x400")

        text = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10,
                       font=('Segoe UI', 10), bg=COR_TERCIARIA)
        text.insert('1.0', help_text.strip())
        text.config(state='disabled')
        text.pack(fill='both', expand=True)

        btn_frame = ttk.Frame(help_window)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="✉️ Contato",
                   command=lambda: webbrowser.open("mailto:suporte@cantinadigital.com.br")).pack(side='left')
        ttk.Button(btn_frame, text="❌ Fechar", command=help_window.destroy).pack(side='right')


def autenticar():
    root = tk.Tk()
    root.withdraw()
    root.tk_setPalette(background=COR_FUNDO)

    tentativas = 3
    while tentativas > 0:
        senha = simpledialog.askstring(
            "🔒 Autenticação",
            f"Digite a senha de administrador ({tentativas} tentativas):",
            show='*',
            parent=root
        )

        if senha == "admin123":  # Em produção, use um método seguro de autenticação
            root.destroy()
            return True
        elif senha is None:
            break

        tentativas -= 1
        messagebox.showerror("Erro", "Senha incorreta!")

    messagebox.showerror("Acesso Negado", "Número máximo de tentativas excedido!")
    root.destroy()
    return False


if __name__ == "__main__":
    if autenticar():
        root = tk.Tk()
        try:
            # Tentar usar tema do Windows se disponível
            root.tk.call("source", "sun-valley.tcl")
            root.tk.call("set_theme", "light")
        except:
            pass

        app = AdminInterface(root)

        # Centralizar a janela
        window_width = root.winfo_reqwidth()
        window_height = root.winfo_reqheight()
        position_right = int(root.winfo_screenwidth() / 2 - window_width / 2)
        position_down = int(root.winfo_screenheight() / 2 - window_height / 2)
        root.geometry(f"+{position_right}+{position_down}")

        root.mainloop()