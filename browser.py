
import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTabWidget,
    QProgressBar,
    QMenuBar,
    QMessageBox,
    QInputDialog,
    QDialog,
    QListWidget,
)
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt6.QtCore import QUrl

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile=None, parent=None):
        super().__init__(profile, parent)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Filtrar mensagens relacionadas ao 'unload'
        if "Unrecognized feature: 'unload'" not in message:
            super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)

class ManageBlockedSitesDialog(QDialog):
    def __init__(self, blocked_sites, remove_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciar Sites Bloqueados")
        self.setMinimumSize(400, 300)
        self.blocked_sites = blocked_sites
        self.remove_callback = remove_callback

        # Layout principal
        layout = QVBoxLayout()

        # Lista de sites bloqueados
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # Botão para remover site selecionado
        self.remove_button = QPushButton("Remover Site Selecionado")
        self.remove_button.clicked.connect(self.remove_selected_site)
        layout.addWidget(self.remove_button)

        # Botão para fechar
        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)

        self.setLayout(layout)

        # Atualizar lista após a criação dos widgets
        self.update_list()

    def update_list(self):
        self.list_widget.clear()
        for url in self.blocked_sites:
            self.list_widget.addItem(url)
        self.remove_button.setEnabled(bool(self.blocked_sites))

    def remove_selected_site(self):
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            url = selected_items[0].text()
            self.remove_callback(url)
            self.update_list()


class DomainBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, blocked_domains):
        super().__init__()
        self.blocked_domains = blocked_domains

    def interceptRequest(self, info):
        from urllib.parse import urlparse
        url = info.requestUrl().toString()
        domain = urlparse(url).netloc.lower()
        for blocked in self.blocked_domains:
            blocked_domain = urlparse(blocked).netloc.lower()
            if blocked_domain and blocked_domain in domain:
                info.block(True)
                return
class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Navegador Avançado")
        self.setGeometry(100, 100, 1200, 800)

        # Lista para armazenar histórico
        self.history = []

        # Carregar favoritos
        self.bookmarks_file = "bookmarks.json"
        self.bookmarks = self.load_bookmarks()

        # Carregar sites bloqueados
        self.blocked_sites_file = "blocked_sites.json"
        self.blocked_sites = self.load_blocked_sites()

        # Perfil para navegação anônima
        self.private_profile = QWebEngineProfile("private_profile", self)
        self.private_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.private_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)

        self.setup_ui()
        self.blocker = DomainBlocker(self.blocked_sites)
        QWebEngineProfile.defaultProfile().setUrlRequestInterceptor(self.blocker)
        self.private_profile.setUrlRequestInterceptor(self.blocker)
        self.setup_menus()
        self.setup_signals()

        # Adicionar aba inicial
        self.add_new_tab(QUrl("https://www.google.com"), "Página Inicial")

    def setup_ui(self):
        # Criar widget de abas
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)

        # Criar barra de navegação
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Digite a URL e pressione Enter")

        self.back_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowBack), "")
        self.back_button.setToolTip("Voltar para página anterior")

        self.forward_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowForward), "")
        self.forward_button.setToolTip("Avançar para próxima página")

        self.reload_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload), "")
        self.reload_button.setToolTip("Recarregar a página atual")

        self.new_tab_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogNewFolder), "")
        self.new_tab_button.setToolTip("Abrir nova aba")

        self.bookmark_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_DialogYesButton), "")
        self.bookmark_button.setToolTip("Adicionar a página atual aos favoritos")

        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)

        # Layout da barra de navegação
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.back_button)
        nav_layout.addWidget(self.forward_button)
        nav_layout.addWidget(self.reload_button)
        nav_layout.addWidget(self.new_tab_button)
        nav_layout.addWidget(self.bookmark_button)
        nav_layout.addWidget(self.url_bar)

        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.tabs)

        # Configurar widget central
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_menus(self):
        # Criar barra de menus
        self.menu_bar = self.menuBar()

        # Menu Arquivo
        self.file_menu = self.menu_bar.addMenu("Arquivo")

        self.new_page_action = QAction("Nova Página", self)
        self.new_page_action.setShortcut("Ctrl+N")
        self.file_menu.addAction(self.new_page_action)

        self.private_tab_action = QAction("Nova Aba Anônima", self)
        self.private_tab_action.setShortcut("Ctrl+Shift+N")
        self.file_menu.addAction(self.private_tab_action)

        self.exit_action = QAction("Sair", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.file_menu.addAction(self.exit_action)

        # Menu Ferramentas
        self.tools_menu = self.menu_bar.addMenu("Ferramentas")
        self.tools_history_menu = self.tools_menu.addMenu("Histórico")

        # Ação para bloquear site
        self.block_site_action = QAction("Bloquear Site", self)
        self.tools_menu.addAction(self.block_site_action)

        # Ação para gerenciar sites bloqueados
        self.manage_blocked_sites_action = QAction("Gerenciar Sites Bloqueados", self)
        self.tools_menu.addAction(self.manage_blocked_sites_action)

        # Ação para limpar histórico
        self.limpar_historico_action = QAction("Limpar Histórico", self)
        self.tools_menu.addAction(self.limpar_historico_action)

        # Menu Favoritos
        self.bookmarks_menu = self.menu_bar.addMenu("Favoritos")
        self.update_bookmarks_menu()

        # Atualizar menu de histórico em Ferramentas
        self.update_history_menu()

    def setup_signals(self):
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_url_bar_on_tab_change)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.back_button.clicked.connect(self.back)
        self.forward_button.clicked.connect(self.forward)
        self.reload_button.clicked.connect(self.reload)
        self.new_tab_button.clicked.connect(self.add_new_tab)
        self.bookmark_button.clicked.connect(self.add_to_bookmarks)
        self.new_page_action.triggered.connect(self.nova_pagina)
        self.private_tab_action.triggered.connect(self.add_new_private_tab)
        self.exit_action.triggered.connect(self.close)
        self.limpar_historico_action.triggered.connect(self.limpar_historico)
        self.block_site_action.triggered.connect(self.block_site)
        self.manage_blocked_sites_action.triggered.connect(self.manage_blocked_sites)

    def load_bookmarks(self):
        try:
            if os.path.exists(self.bookmarks_file):
                with open(self.bookmarks_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [b for b in data if isinstance(b, dict) and "title" in b and "url" in b]
            return []
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(self, "Erro", f"Falha ao carregar favoritos: {e}")
            return []

    def save_bookmarks(self):
        try:
            with open(self.bookmarks_file, "w") as f:
                json.dump(self.bookmarks, f, indent=4)
        except IOError as e:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar favoritos: {e}")

    def load_blocked_sites(self):
        try:
            if os.path.exists(self.blocked_sites_file):
                with open(self.blocked_sites_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [url for url in data if isinstance(url, str)]
            return []
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(self, "Erro", f"Falha ao carregar lista de sites bloqueados: {e}")
            return []

    def save_blocked_sites(self):
        try:
            with open(self.blocked_sites_file, "w") as f:
                json.dump(self.blocked_sites, f, indent=4)
        except IOError as e:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar lista de sites bloqueados: {e}")

    def block_site(self):
        url, ok = QInputDialog.getText(self, "Bloquear Site", "Digite a URL do site a ser bloqueado (ex: https://example.com):")
        if ok and url:
            # Normalizar a URL (remover espaços e garantir formato)
            url = url.strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            qurl = QUrl(url)
            if not qurl.isValid():
                QMessageBox.warning(self, "URL Inválida", "Por favor, insira uma URL válida.")
                return
            normalized_url = qurl.toString(QUrl.UrlFormattingOption.FullyDecoded)
            if normalized_url not in self.blocked_sites:
                self.blocked_sites.append(normalized_url)
                self.save_blocked_sites()
                QMessageBox.information(self, "Site Bloqueado", f"O site {url} foi adicionado à lista de bloqueio.")
            else:
                QMessageBox.information(self, "Site Já Bloqueado", f"O site {url} já está na lista de bloqueio.")

    def manage_blocked_sites(self):
        dialog = ManageBlockedSitesDialog(self.blocked_sites, self.remove_blocked_site, self)
        dialog.exec()

    def remove_blocked_site(self, url):
        if url in self.blocked_sites:
            self.blocked_sites.remove(url)
            self.save_blocked_sites()
            QMessageBox.information(self, "Site Removido", f"O site {url} foi removido da lista de bloqueio.")

    def update_bookmarks_menu(self):
        self.bookmarks_menu.clear()
        if not self.bookmarks:
            action = QAction("Nenhum favorito", self)
            action.setEnabled(False)
            self.bookmarks_menu.addAction(action)
        self.bookmarks_menu.setEnabled(bool(self.bookmarks))
        for bookmark in self.bookmarks:
            if isinstance(bookmark, dict) and "title" in bookmark and "url" in bookmark:
                action = QAction(bookmark["title"], self)
                action.setData(bookmark["url"])
                action.triggered.connect(self.navigate_to_bookmark)
                self.bookmarks_menu.addAction(action)

    def add_to_bookmarks(self):
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            url = current_web_view.url().toString()
            title = current_web_view.title() or "Sem Título"
            if url and url not in [b["url"] for b in self.bookmarks]:
                self.bookmarks.append({"title": title, "url": url})
                self.save_bookmarks()
                self.update_bookmarks_menu()
                QMessageBox.information(self, "Favorito Adicionado", f"{title} foi adicionado aos favoritos.")

    def navigate_to_bookmark(self):
        action = self.sender()
        if action:
            url = action.data()
            current_web_view = self.tabs.currentWidget()
            if current_web_view:
                current_web_view.setUrl(QUrl(url))

    def add_new_tab(self, qurl=None, label="Nova Aba"):
        if qurl is None or not isinstance(qurl, QUrl):
            qurl = QUrl("https://www.google.com")
        web_view = QWebEngineView()
        page = CustomWebEnginePage(parent=web_view)
        web_view.setPage(page)
        web_view.setUrl(qurl)
        web_view.urlChanged.connect(self.update_url_bar)
        web_view.loadProgress.connect(self.update_progress_bar)
        web_view.loadFinished.connect(self.hide_progress_bar)
        web_view.titleChanged.connect(lambda title: self.tabs.setTabText(self.tabs.indexOf(web_view), title or "Nova Aba"))
        web_view.urlChanged.connect(self.add_to_history)
        index = self.tabs.addTab(web_view, label)
        self.tabs.setCurrentIndex(index)
        return web_view

    def add_new_private_tab(self):
        web_view = QWebEngineView()
        page = CustomWebEnginePage(self.private_profile, parent=web_view)
        web_view.setPage(page)
        web_view.setUrl(QUrl("https://www.google.com"))
        web_view.urlChanged.connect(self.update_url_bar)
        web_view.loadProgress.connect(self.update_progress_bar)
        web_view.loadFinished.connect(self.hide_progress_bar)
        web_view.titleChanged.connect(lambda title: self.tabs.setTabText(self.tabs.indexOf(web_view), title or "Nova Aba Anônima"))
        index = self.tabs.addTab(web_view, "Nova Aba Anônima")
        self.tabs.setCurrentIndex(index)
        return web_view

    def close_tab(self, index):
        if self.tabs.count() > 1:
            web_view = self.tabs.widget(index)
            if web_view:
                web_view.urlChanged.disconnect()
                web_view.loadProgress.disconnect()
                web_view.loadFinished.disconnect()
                web_view.titleChanged.disconnect()
                if web_view.page().profile() != self.private_profile:
                    try:
                        web_view.urlChanged.disconnect(self.add_to_history)
                    except TypeError:
                        pass  # Já desconectado ou não conectado
            self.tabs.removeTab(index)

    def navigate_to_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text:
            QMessageBox.warning(self, "URL Inválida", "Por favor, insira uma URL.")
            return
        qurl = QUrl(url_text)
        if not qurl.scheme():
            qurl = QUrl("https://" + url_text)
        if not qurl.isValid():
            QMessageBox.warning(self, "URL Inválida", "A URL fornecida é inválida ou malformada.")
            return
        # Verificar se a URL está na lista de sites bloqueados
        normalized_url = qurl.toString(QUrl.UrlFormattingOption.FullyDecoded)
        if normalized_url in self.blocked_sites:
            QMessageBox.warning(self, "Acesso Bloqueado", "Este site contém conteúdo perigoso e está bloqueado.")
            return
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            current_web_view.setUrl(qurl)

    def update_url_bar(self, qurl):
        current_web_view = self.tabs.currentWidget()
        if current_web_view and current_web_view == self.sender():
            self.url_bar.setText(qurl.toString())

    def update_url_bar_on_tab_change(self, index):
        web_view = self.tabs.widget(index)
        if web_view:
            self.url_bar.setText(web_view.url().toString())

    def update_progress_bar(self, progress):
        current_web_view = self.tabs.currentWidget()
        if current_web_view and current_web_view == self.sender():
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(progress)

    def hide_progress_bar(self):
        current_web_view = self.tabs.currentWidget()
        if current_web_view and current_web_view == self.sender():
            self.progress_bar.setVisible(False)

    def back(self):
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            current_web_view.back()

    def forward(self):
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            current_web_view.forward()

    def reload(self):
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            current_web_view.setUrl(current_web_view.url())  # Forçar recarregamento

    def add_to_history(self, qurl):
        current_web_view = self.tabs.currentWidget()
        if current_web_view and current_web_view == self.sender():
            if current_web_view.page().profile() != self.private_profile:
                url = qurl.toString()
                title = current_web_view.title() or "Sem Título"
                if url and url not in [h["url"] for h in self.history[-10:]]:
                    self.history.append({"title": title, "url": url})
                    self.update_history_menu()

    def update_history_menu(self):
        self.tools_history_menu.clear()
        if not self.history:
            action = QAction("Nenhum histórico", self)
            action.setEnabled(False)
            self.tools_history_menu.addAction(action)
        else:
            for entry in self.history[-10:]:
                if isinstance(entry, dict) and "title" in entry and "url" in entry:
                    action = QAction(entry["title"], self)
                    action.setData(entry["url"])
                    action.triggered.connect(self.navigate_to_history)
                    self.tools_history_menu.addAction(action)
        self.tools_history_menu.setEnabled(bool(self.history))

    def navigate_to_history(self):
        action = self.sender()
        if action:
            url = action.data()
            current_web_view = self.tabs.currentWidget()
            if current_web_view:
                current_web_view.setUrl(QUrl(url))

    def limpar_historico(self):
        self.history.clear()
        self.update_history_menu()
        QMessageBox.information(self, "Histórico", "Histórico apagado com sucesso.")

    def nova_pagina(self):
        self.add_new_tab()

    def closeEvent(self, event):
        self.save_bookmarks()
        self.save_blocked_sites()
        super().closeEvent(event)

if __name__ == "__main__":
    # Evitar múltiplas instâncias do QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    browser = Browser()
    browser.show()
    sys.exit(app.exec())
