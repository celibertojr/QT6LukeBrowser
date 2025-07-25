import sys
import json
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse
import re
import idna
from io import TextIOWrapper
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
    QListWidgetItem,
    QLabel,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QFileDialog,
)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineUrlRequestInterceptor
from PyQt6.QtCore import QUrl, QThread, pyqtSignal, QObject

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile=None, parent=None):
        super().__init__(profile, parent)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        silenced = [
            "Unrecognized feature:",
            "non-JS module files deprecated",
            "Deprecated API",
            "Permissions-Policy",
            "crbug/"
        ]
        if not any(s in message for s in silenced):
            super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)

class SettingsDialog(QDialog):
    def __init__(self, settings_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumSize(400, 400)
        self.settings_file = settings_file
        self.settings = self.load_settings()
        
        layout = QVBoxLayout()
        
        self.max_domains_label = QLabel("Limite Máximo de Domínios (MAX_DOMAINS):")
        layout.addWidget(self.max_domains_label)
        self.max_domains_input = QSpinBox()
        self.max_domains_input.setRange(1000, 1000000)
        self.max_domains_input.setValue(self.settings.get("max_domains", 50000))
        layout.addWidget(self.max_domains_input)
        
        self.batch_size_label = QLabel("Tamanho do Lote (BATCH_SIZE):")
        layout.addWidget(self.batch_size_label)
        self.batch_size_input = QSpinBox()
        self.batch_size_input.setRange(50, 1000)
        self.batch_size_input.setValue(self.settings.get("batch_size", 200))
        layout.addWidget(self.batch_size_input)
        
        self.validation_mode_label = QLabel("Modo de Validação de Domínios:")
        layout.addWidget(self.validation_mode_label)
        self.validation_mode_input = QComboBox()
        self.validation_mode_input.addItems(["Rigorosa", "Relaxada", "Personalizada"])
        self.validation_mode_input.setCurrentText(self.settings.get("validation_mode", "Rigorosa"))
        layout.addWidget(self.validation_mode_input)
        
        self.custom_validation_url_label = QLabel("URLs para Validação Relaxada (separadas por vírgula):")
        layout.addWidget(self.custom_validation_url_label)
        self.custom_validation_url_input = QLineEdit()
        self.custom_validation_url_input.setText(",".join(self.settings.get("custom_validation_urls", [])))
        self.custom_validation_url_input.setEnabled(self.validation_mode_input.currentText() == "Personalizada")
        layout.addWidget(self.custom_validation_url_input)
        
        self.adblock_support_label = QLabel("Suporte a Formato Adblock Plus:")
        layout.addWidget(self.adblock_support_label)
        self.adblock_support_input = QCheckBox("Habilitar")
        self.adblock_support_input.setChecked(self.settings.get("adblock_support", False))
        layout.addWidget(self.adblock_support_input)
        
        self.retries_label = QLabel("Número de Tentativas de Conexão:")
        layout.addWidget(self.retries_label)
        self.retries_input = QSpinBox()
        self.retries_input.setRange(1, 5)
        self.retries_input.setValue(self.settings.get("retries", 3))
        layout.addWidget(self.retries_input)
        
        self.sleep_time_label = QLabel("Pausa entre Lotes (ms):")
        layout.addWidget(self.sleep_time_label)
        self.sleep_time_input = QSpinBox()
        self.sleep_time_input.setRange(0, 50)
        self.sleep_time_input.setValue(self.settings.get("sleep_time", 5))
        layout.addWidget(self.sleep_time_input)
        
        self.rejected_limit_label = QLabel("Limite de Domínios Rejeitados Exibidos na UI:")
        layout.addWidget(self.rejected_limit_label)
        self.rejected_limit_input = QSpinBox()
        self.rejected_limit_input.setRange(5, 50)
        self.rejected_limit_input.setValue(self.settings.get("rejected_limit", 5))
        layout.addWidget(self.rejected_limit_input)
        
        self.whitelist_enabled_label = QLabel("Habilitar Whitelist:")
        layout.addWidget(self.whitelist_enabled_label)
        self.whitelist_enabled_input = QCheckBox("Habilitar")
        self.whitelist_enabled_input.setChecked(self.settings.get("whitelist_enabled", True))
        layout.addWidget(self.whitelist_enabled_input)
        
        self.save_mode_label = QLabel("Modo de Salvamento de blocked_sites.json:")
        layout.addWidget(self.save_mode_label)
        self.save_mode_input = QComboBox()
        self.save_mode_input.addItems(["Incremental", "Único"])
        self.save_mode_input.setCurrentText(self.settings.get("save_mode", "Incremental"))
        layout.addWidget(self.save_mode_input)
        
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.validation_mode_input.currentTextChanged.connect(self.toggle_custom_validation)

    def load_settings(self):
        default_settings = {
            "max_domains": 50000,
            "batch_size": 200,
            "validation_mode": "Rigorosa",
            "custom_validation_urls": [],
            "adblock_support": False,
            "retries": 3,
            "sleep_time": 5,
            "rejected_limit": 5,
            "whitelist_enabled": True,
            "save_mode": "Incremental"
        }
        try:
            if not os.path.exists(self.settings_file):
                print(f"Arquivo {self.settings_file} não existe. Criando com configurações padrão.")
                try:
                    with open(self.settings_file, "w") as f:
                        json.dump(default_settings, f, indent=4)
                except IOError as e:
                    print(f"Erro ao criar {self.settings_file}: {e}")
                    return default_settings
            if not os.access(self.settings_file, os.R_OK | os.W_OK):
                print(f"Aviso: Permissões insuficientes para acessar {self.settings_file}")
                return default_settings
            with open(self.settings_file, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                print(f"Erro: {self.settings_file} contém dados inválidos. Retornando configurações padrão.")
                return default_settings
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar configurações de {self.settings_file}: {e}")
            return default_settings

    def save_settings(self):
        settings = {
            "max_domains": self.max_domains_input.value(),
            "batch_size": self.batch_size_input.value(),
            "validation_mode": self.validation_mode_input.currentText(),
            "custom_validation_urls": [url.strip() for url in self.custom_validation_url_input.text().split(",") if url.strip()],
            "adblock_support": self.adblock_support_input.isChecked(),
            "retries": self.retries_input.value(),
            "sleep_time": self.sleep_time_input.value(),
            "rejected_limit": self.rejected_limit_input.value(),
            "whitelist_enabled": self.whitelist_enabled_input.isChecked(),
            "save_mode": self.save_mode_input.currentText()
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings, f, indent=4)
            QMessageBox.information(self, "Configurações", "Configurações salvas com sucesso.")
            self.accept()
        except IOError as e:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar configurações: {e}")

    def toggle_custom_validation(self, mode):
        self.custom_validation_url_input.setEnabled(mode == "Personalizada")

class ListImportWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(int, str, list)
    error = pyqtSignal(str)

    def __init__(self, list_url, blocked_sites, blocked_lists, blocked_sites_file, whitelist, settings):
        super().__init__()
        self.list_url = list_url
        self.blocked_sites = blocked_sites
        self.blocked_lists = blocked_lists
        self.blocked_sites_file = blocked_sites_file
        self.whitelist = whitelist
        self.settings = settings
        self.cancelled = False
        self.MAX_DOMAINS = self.settings.get("max_domains", 50000)
        self.BATCH_SIZE = self.settings.get("batch_size", 200)
        self.rejected_domains = []

    def cancel(self):
        self.cancelled = True

    def normalize_domain(self, domain):
        domain = domain.strip().lower()
        domain = re.sub(r'^https?://', '', domain)
        domain = domain.split('/')[0]
        if not domain or domain.startswith('localhost'):
            self.rejected_domains.append(domain)
            print(f"Aviso: Domínio inválido rejeitado: {domain}")
            return None
        if self.settings.get("whitelist_enabled", True) and domain in self.whitelist:
            self.rejected_domains.append(domain)
            print(f"Aviso: Domínio na whitelist rejeitado: {domain}")
            return None
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', domain):
            return domain
        if any(ord(c) > 127 for c in domain):
            try:
                domain = idna.encode(domain).decode('ascii')
            except idna.IDNAError:
                self.rejected_domains.append(domain)
                print(f"Aviso: Falha ao converter IDN: {domain}")
                return None
        validation_mode = self.settings.get("validation_mode", "Rigorosa")
        if validation_mode == "Relaxada" or (validation_mode == "Personalizada" and any(url in self.list_url for url in self.settings.get("custom_validation_urls", []))):
            return domain
        if 'KADhosts' in self.list_url:
            return domain
        if re.match(r'^[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]*)*\.[a-z0-9]{1,}$', domain):
            return domain
        self.rejected_domains.append(domain)
        print(f"Aviso: Domínio inválido rejeitado: {domain}")
        return None

    def append_to_blocked_sites_file(self, domains):
        if self.settings.get("save_mode", "Incremental") == "Incremental":
            try:
                if not os.path.exists(self.blocked_sites_file):
                    with open(self.blocked_sites_file, 'w') as f:
                        json.dump([], f)
                with open(self.blocked_sites_file, 'r+') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
                    data.extend(domains)
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
            except IOError as e:
                print(f"Erro ao salvar domínios em {self.blocked_sites_file}: {e}")

    def save_all_domains(self, domains):
        try:
            with open(self.blocked_sites_file, 'w') as f:
                json.dump(domains, f, indent=4)
        except IOError as e:
            print(f"Erro ao salvar domínios em {self.blocked_sites_file}: {e}")

    def run(self):
        try:
            if not self.list_url.startswith("http://") and not self.list_url.startswith("https://"):
                self.list_url = "https://" + self.list_url
            if not QUrl(self.list_url).isValid():
                self.error.emit("URL inválida para a lista de bloqueio.")
                return

            if self.list_url not in self.blocked_lists:
                self.blocked_lists.append(self.list_url)

            is_url_list = self.list_url.endswith('.txt')
            new_domains = []
            domain_count = 0
            added_count = 0
            batch = set()

            self.progress.emit(0, "Baixando lista principal...")
            retries = self.settings.get("retries", 3)
            for attempt in range(retries):
                try:
                    with urllib.request.urlopen(self.list_url) as response:
                        total_size = response.getheader('Content-Length')
                        total_lines = int(total_size) // 50 if total_size else 50000
                        processed_lines = 0

                        if is_url_list:
                            reader = TextIOWrapper(response, encoding='utf-8')
                            for line in reader:
                                if self.cancelled:
                                    if batch:
                                        self.append_to_blocked_sites_file(list(batch))
                                    self.finished.emit(added_count, "Importação cancelada.", self.rejected_domains)
                                    return
                                line = line.strip()
                                processed_lines += 1
                                if line and not line.startswith('#') and not line.startswith('!'):
                                    parts = line.split()
                                    domain = None
                                    if self.settings.get("adblock_support", False) and line.startswith('||') and line.endswith('^'):
                                        domain = line[2:-1].strip()
                                    elif len(parts) >= 2 and parts[0] in ('0.0.0.0', '127.0.0.1'):
                                        domain = parts[1].strip()
                                    elif len(parts) == 1:
                                        domain = parts[0].strip()
                                    if domain:
                                        normalized = self.normalize_domain(domain)
                                        if normalized and normalized not in batch and normalized not in self.blocked_sites:
                                            batch.add(normalized)
                                            domain_count += 1
                                            if len(batch) >= self.BATCH_SIZE:
                                                self.blocked_sites.extend(batch)
                                                self.append_to_blocked_sites_file(list(batch))
                                                added_count += len(batch)
                                                batch.clear()
                                                progress = min(100, int((processed_lines / total_lines) * 100))
                                                self.progress.emit(progress, f"Processando domínio {domain_count}/{total_lines}")
                                                QThread.msleep(self.settings.get("sleep_time", 5))
                                            if domain_count >= self.MAX_DOMAINS:
                                                self.progress.emit(100, f"Limite de {self.MAX_DOMAINS} domínios atingido.")
                                                break
                            if batch:
                                self.blocked_sites.extend(batch)
                                self.append_to_blocked_sites_file(list(batch))
                                added_count += len(batch)
                        else:
                            content = response.read().decode('utf-8')
                            lines = [line.strip() for line in content.splitlines() if line.startswith('http')]
                            total_urls = len(lines)
                            for i, url in enumerate(lines):
                                if self.cancelled:
                                    if batch:
                                        self.append_to_blocked_sites_file(list(batch))
                                    self.finished.emit(added_count, "Importação cancelada.", self.rejected_domains)
                                    return
                                if not QUrl(url).isValid():
                                    print(f"Aviso: URL inválida ignorada: {url}")
                                    continue
                                self.progress.emit(int((i / total_urls) * 50), f"Processando sublista {i + 1}/{total_urls}")
                                for attempt in range(retries):
                                    try:
                                        with urllib.request.urlopen(url) as sub_response:
                                            sub_reader = TextIOWrapper(sub_response, encoding='utf-8')
                                            for line in sub_reader:
                                                if self.cancelled:
                                                    if batch:
                                                        self.append_to_blocked_sites_file(list(batch))
                                                    self.finished.emit(added_count, "Importação cancelada.", self.rejected_domains)
                                                    return
                                                line = line.strip()
                                                if line and not line.startswith('#') and not line.startswith('!'):
                                                    parts = line.split()
                                                    domain = None
                                                    if self.settings.get("adblock_support", False) and line.startswith('||') and line.endswith('^'):
                                                        domain = line[2:-1].strip()
                                                    elif len(parts) >= 2 and parts[0] in ('0.0.0.0', '127.0.0.1'):
                                                        domain = parts[1].strip()
                                                    elif len(parts) == 1:
                                                        domain = parts[0].strip()
                                                    if domain:
                                                        normalized = self.normalize_domain(domain)
                                                        if normalized and normalized not in batch and normalized not in self.blocked_sites:
                                                            batch.add(normalized)
                                                            domain_count += 1
                                                            if len(batch) >= self.BATCH_SIZE:
                                                                self.blocked_sites.extend(batch)
                                                                self.append_to_blocked_sites_file(list(batch))
                                                                added_count += len(batch)
                                                                batch.clear()
                                                                progress = 50 + int(((i + 1) / total_urls) * 50)
                                                                self.progress.emit(progress, f"Processando domínio {domain_count}")
                                                                QThread.msleep(self.settings.get("sleep_time", 5))
                                                            if domain_count >= self.MAX_DOMAINS:
                                                                self.progress.emit(100, f"Limite de {self.MAX_DOMAINS} domínios atingido.")
                                                                break
                                            break
                                    except urllib.error.URLError as e:
                                        if attempt == retries - 1:
                                            print(f"Erro ao processar URL {url} após {retries} tentativas: {e}")
                                        QThread.msleep(1000)
                                        continue
                                if domain_count >= self.MAX_DOMAINS:
                                    break
                        break
                except urllib.error.URLError as e:
                    if attempt == retries - 1:
                        self.error.emit(f"Falha após {retries} tentativas: {e}")
                        return
                    QThread.msleep(1000)
                    continue

            if domain_count == 0:
                self.error.emit("Nenhum domínio válido encontrado na lista.")
                return

            if self.settings.get("save_mode", "Incremental") == "Único" and new_domains:
                self.blocked_sites.extend(new_domains)
                self.save_all_domains(self.blocked_sites)

            self.finished.emit(added_count, f"{added_count} domínios adicionados à lista de bloqueio.", self.rejected_domains)
        except Exception as e:
            self.error.emit(f"Falha ao importar lista de bloqueio: {e}")

class ImportBlockListsDialog(QDialog):
    def __init__(self, import_callback, blocked_sites, blocked_lists, blocked_sites_file, whitelist, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar Listas de Bloqueio")
        self.setMinimumSize(400, 300)
        self.import_callback = import_callback
        self.blocked_sites = blocked_sites
        self.blocked_lists = blocked_lists
        self.blocked_sites_file = blocked_sites_file
        self.whitelist = whitelist
        self.settings = settings
        self.worker_thread = None

        layout = QVBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Digite a URL da lista de bloqueio (ex: https://raw.githubusercontent.com/PolishFiltersTeam/KADhosts/master/KADhosts.txt)")
        layout.addWidget(self.url_input)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto para importar.")
        layout.addWidget(self.status_label)

        self.rejected_label = QLabel("")
        self.rejected_label.setWordWrap(True)
        self.rejected_label.setVisible(False)
        layout.addWidget(self.rejected_label)

        button_layout = QHBoxLayout()
        self.import_button = QPushButton("Importar Lista")
        self.import_button.clicked.connect(self.start_import)
        button_layout.addWidget(self.import_button)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.cancel_import)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self.close_dialog)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def start_import(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Erro", "Por favor, insira uma URL.")
            return
        self.url_input.setEnabled(False)
        self.import_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Iniciando importação...")
        self.rejected_label.setVisible(False)

        self.worker_thread = QThread()
        self.worker = ListImportWorker(url, self.blocked_sites, self.blocked_lists, self.blocked_sites_file, self.whitelist, self.settings)
        self.worker.moveToThread(self.worker_thread)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.error.connect(self.import_error)
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def import_finished(self, count, message, rejected_domains):
        self.progress_bar.setValue(100)
        self.status_label.setText(message)
        if rejected_domains:
            rejected_limit = self.settings.get("rejected_limit", 5)
            self.rejected_label.setText(f"Domínios rejeitados ({len(rejected_domains)}): {', '.join(rejected_domains[:rejected_limit])}{'...' if len(rejected_domains) > rejected_limit else ''}")
            self.rejected_label.setVisible(True)
        self.import_callback()
        self.cleanup_thread()
        QMessageBox.information(self, "Sucesso", message)

    def import_error(self, message):
        self.status_label.setText("Erro na importação.")
        self.rejected_label.setVisible(False)
        self.cleanup_thread()
        QMessageBox.warning(self, "Erro", message)

    def cancel_import(self):
        if self.worker_thread and self.worker:
            self.worker.cancel()
            self.status_label.setText("Cancelando importação...")
            self.cancel_button.setEnabled(False)

    def cleanup_thread(self):
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None
        self.url_input.setEnabled(True)
        self.import_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)

    def close_dialog(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.cancel_import()
        self.accept()

class ManageBlockedSitesDialog(QDialog):
    def __init__(self, blocked_sites, blocked_lists, whitelist, remove_site_callback, remove_list_callback, add_to_whitelist_callback, remove_from_whitelist_callback, parent=None):
        super().__init__(parent)
        print("Inicializando ManageBlockedSitesDialog")  # Log de depuração
        self.setWindowTitle("Gerenciar Sites e Listas")
        self.setMinimumSize(400, 400)
        self.blocked_sites = blocked_sites or []
        self.blocked_lists = blocked_lists or []
        self.whitelist = whitelist or []
        self.remove_site_callback = remove_site_callback
        self.remove_list_callback = remove_list_callback
        self.add_to_whitelist_callback = add_to_whitelist_callback
        self.remove_from_whitelist_callback = remove_from_whitelist_callback

        layout = QVBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Digite para filtrar sites, listas ou whitelist...")
        self.search_input.textChanged.connect(self.filter_lists)
        layout.addWidget(self.search_input)
        
        self.sites_label = QLabel("Sites Bloqueados:")
        layout.addWidget(self.sites_label)
        self.sites_list_widget = QListWidget()
        self.sites_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.sites_list_widget)
        
        self.lists_label = QLabel("Listas de Bloqueio Importadas:")
        layout.addWidget(self.lists_label)
        self.lists_list_widget = QListWidget()
        self.lists_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.lists_list_widget)

        self.whitelist_label = QLabel("Lista de Permissões (Whitelist):")
        layout.addWidget(self.whitelist_label)
        self.whitelist_list_widget = QListWidget()
        self.whitelist_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.whitelist_list_widget)

        self.remove_site_button = QPushButton("Remover Site Selecionado")
        self.remove_site_button.clicked.connect(self.remove_selected_site)
        layout.addWidget(self.remove_site_button)

        self.add_to_whitelist_button = QPushButton("Adicionar Site à Whitelist")
        self.add_to_whitelist_button.clicked.connect(self.add_to_whitelist)
        layout.addWidget(self.add_to_whitelist_button)

        self.remove_from_whitelist_button = QPushButton("Remover Site da Whitelist")
        self.remove_from_whitelist_button.clicked.connect(self.remove_from_whitelist)
        layout.addWidget(self.remove_from_whitelist_button)

        self.remove_list_button = QPushButton("Remover Lista Selecionada")
        self.remove_list_button.clicked.connect(self.remove_selected_list)
        layout.addWidget(self.remove_list_button)

        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)

        self.setLayout(layout)
        self.update_lists()
        print("ManageBlockedSitesDialog inicializado com sucesso")  # Log de depuração

    def update_lists(self):
        print(f"Atualizando listas: blocked_sites={len(self.blocked_sites)}, blocked_lists={len(self.blocked_lists)}, whitelist={len(self.whitelist)}")  # Log de depuração
        self.sites_list_widget.clear()
        for url in self.blocked_sites:
            self.sites_list_widget.addItem(url)
        self.lists_list_widget.clear()
        for list_url in self.blocked_lists:
            item = QListWidgetItem(list_url)
            self.lists_list_widget.addItem(item)
        self.whitelist_list_widget.clear()
        for url in self.whitelist:
            self.whitelist_list_widget.addItem(url)
        self.remove_site_button.setEnabled(bool(self.sites_list_widget.count()))
        self.remove_list_button.setEnabled(bool(self.lists_list_widget.count()))
        self.remove_from_whitelist_button.setEnabled(bool(self.whitelist_list_widget.count()))
        print("Listas atualizadas na UI")  # Log de depuração

    def filter_lists(self, text):
        print(f"Filtrando listas com texto: {text}")  # Log de depuração
        text = text.lower().strip()
        self.sites_list_widget.clear()
        self.lists_list_widget.clear()
        self.whitelist_list_widget.clear()
        
        # Filtrar sites bloqueados
        for url in self.blocked_sites:
            if not text or text in url.lower():
                self.sites_list_widget.addItem(url)
        
        # Filtrar listas de bloqueio
        for list_url in self.blocked_lists:
            if not text or text in list_url.lower():
                item = QListWidgetItem(list_url)
                self.lists_list_widget.addItem(item)
        
        # Filtrar whitelist
        for url in self.whitelist:
            if not text or text in url.lower():
                self.whitelist_list_widget.addItem(url)
        
        self.remove_site_button.setEnabled(bool(self.sites_list_widget.count()))
        self.remove_list_button.setEnabled(bool(self.lists_list_widget.count()))
        self.remove_from_whitelist_button.setEnabled(bool(self.whitelist_list_widget.count()))
        print("Listas filtradas na UI")  # Log de depuração

    def remove_selected_site(self):
        print("Botão Remover Site Selecionado clicado")  # Log de depuração
        selected_items = self.sites_list_widget.selectedItems()
        if selected_items:
            removed_urls = [item.text() for item in selected_items]
            for url in removed_urls:
                self.remove_site_callback(url)
            self.update_lists()
            QMessageBox.information(self, "Sites Removidos", f"{len(removed_urls)} site(s) removido(s) da lista de bloqueio.")

    def add_to_whitelist(self):
        print("Botão Adicionar Site à Whitelist clicado")  # Log de depuração
        url, ok = QInputDialog.getText(self, "Adicionar à Whitelist", "Digite o domínio para adicionar à whitelist (ex: alohafromdeer.com):")
        if ok and url:
            normalized = self.normalize_domain(url)
            if normalized and normalized not in self.whitelist:
                self.add_to_whitelist_callback(normalized)
                self.update_lists()
                QMessageBox.information(self, "Whitelist", f"{normalized} adicionado à whitelist.")

    def remove_from_whitelist(self):
        print("Botão Remover Site da Whitelist clicado")  # Log de depuração
        selected_items = self.whitelist_list_widget.selectedItems()
        if selected_items:
            removed_urls = [item.text() for item in selected_items]
            for url in removed_urls:
                self.remove_from_whitelist_callback(url)
            self.update_lists()
            QMessageBox.information(self, "Whitelist", f"{len(removed_urls)} site(s) removido(s) da whitelist.")

    def remove_selected_list(self):
        print("Botão Remover Lista Selecionada clicado")  # Log de depuração
        selected_items = self.lists_list_widget.selectedItems()
        if selected_items:
            removed_urls = [item.text() for item in selected_items]
            for url in removed_urls:
                self.remove_list_callback(url)
            self.update_lists()
            QMessageBox.information(self, "Listas Removidas", f"{len(removed_urls)} lista(s) removida(s).")

    def normalize_domain(self, domain):
        domain = domain.strip().lower()
        domain = re.sub(r'^https?://', '', domain)
        domain = domain.split('/')[0]
        if not domain or domain.startswith('localhost'):
            return None
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', domain):
            return domain
        if any(ord(c) > 127 for c in domain):
            try:
                domain = idna.encode(domain).decode('ascii')
            except idna.IDNAError:
                return None
        if re.match(r'^[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]*)*\.[a-z0-9]{1,}$', domain):
            return domain
        return None

class DomainBlocker(QWebEngineUrlRequestInterceptor):
    def __init__(self, blocked_domains, whitelist, settings):
        super().__init__()
        self.blocked_domains = blocked_domains
        self.whitelist = whitelist
        self.settings = settings

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        domain = urlparse(url).netloc.lower()
        if self.settings.get("whitelist_enabled", True) and domain in self.whitelist:
            return
        for blocked in self.blocked_domains:
            blocked_domain = urlparse(blocked).netloc.lower() or blocked.lower()
            if blocked_domain and (blocked_domain == domain or domain.endswith('.' + blocked_domain)):
                info.block(True)
                web_view = self.sender().view() if hasattr(self.sender(), 'view') else None
                if web_view:
                    web_view.setHtml("""
                        <html>
                        <body style='background-color: #f5f5f5; color: #333333; text-align: center; padding: 50px;'>
                            <h1>Site Bloqueado</h1>
                            <p>Este site está na lista de bloqueio.</p>
                        </body>
                        </html>
                    """)
                print(f"Bloqueando URL: {url} (domínio: {blocked_domain})")
                return

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Navegador Avançado")
        self.setGeometry(100, 100, 1200, 800)

        self.history = []
        self.bookmarks_file = "bookmarks.json"
        self.bookmarks = self.load_bookmarks()
        self.settings_file = "settings.json"
        self.settings = self.load_settings()
        self.blocked_sites_file = "blocked_sites.json"
        self.blocked_sites = self.load_blocked_sites()
        self.blocked_lists_file = "blocked_lists.json"
        self.blocked_lists = self.load_blocked_lists()
        self.whitelist_file = "whitelist.json"
        self.whitelist = self.load_whitelist()

        self.private_profile = QWebEngineProfile("private_profile", self)
        self.private_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.private_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)

        self.setup_ui()
        if self.tabs is None:
            raise RuntimeError("QTabWidget não foi inicializado corretamente em setup_ui")
        self.blocker = DomainBlocker(self.blocked_sites, self.whitelist, self.settings)
        QWebEngineProfile.defaultProfile().setUrlRequestInterceptor(self.blocker)
        self.private_profile.setUrlRequestInterceptor(self.blocker)
        self.setup_menus()
        self.setup_signals()
        self.add_new_tab(QUrl("https://www.google.com"), "Página Inicial")

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Digite a URL e pressione Enter")

        self.back_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowBack), "")
        self.back_button.setToolTip("Voltar para página anterior")

        self.forward_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowForward), "")
        self.forward_button.setToolTip("Avançar para próxima página")

        self.reload_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload), "")
        self.reload_button.setToolTip("Recarregar a página atual")

        self.home_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_DirHomeIcon), "")
        self.home_button.setToolTip("Ir para a página inicial (Google)")

        self.new_tab_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogNewFolder), "")
        self.new_tab_button.setToolTip("Abrir nova aba")

        private_icon_path = "private.png"
        if os.path.exists(private_icon_path):
            self.new_private_tab_button = QPushButton(QIcon(private_icon_path), "")
        else:
            self.new_private_tab_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon), "")
        self.new_private_tab_button.setToolTip("Abrir aba anônima")

        self.bookmark_button = QPushButton(self.style().standardIcon(self.style().StandardPixmap.SP_DialogYesButton), "")
        self.bookmark_button.setToolTip("Adicionar a página atual aos favoritos")

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)

        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.back_button)
        nav_layout.addWidget(self.forward_button)
        nav_layout.addWidget(self.reload_button)
        nav_layout.addWidget(self.home_button)
        nav_layout.addWidget(self.new_tab_button)
        nav_layout.addWidget(self.new_private_tab_button)
        nav_layout.addWidget(self.bookmark_button)
        nav_layout.addWidget(self.url_bar)

        main_layout = QVBoxLayout()
        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_menus(self):
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("Arquivo")

        self.new_page_action = QAction("Nova Página", self)
        self.new_page_action.setShortcut("Ctrl+N")
        self.file_menu.addAction(self.new_page_action)

        self.private_tab_action = QAction("Nova Aba Anônima", self)
        self.private_tab_action.setShortcut("Ctrl+Shift+N")
        self.file_menu.addAction(self.private_tab_action)

        # Sub-menu para Gerenciar Listas
        self.lists_menu = self.file_menu.addMenu("Gerenciar Listas")
        
        self.export_blocked_sites_action = QAction("Exportar Lista de Sites Bloqueados", self)
        self.lists_menu.addAction(self.export_blocked_sites_action)
        
        self.import_blocked_sites_action = QAction("Importar Lista de Sites Bloqueados", self)
        self.lists_menu.addAction(self.import_blocked_sites_action)
        
        self.export_blocked_lists_action = QAction("Exportar Listas de Bloqueio", self)
        self.lists_menu.addAction(self.export_blocked_lists_action)
        
        self.import_blocked_lists_action = QAction("Importar Listas de Bloqueio", self)
        self.lists_menu.addAction(self.import_blocked_lists_action)
        
        self.export_whitelist_action = QAction("Exportar Whitelist", self)
        self.lists_menu.addAction(self.export_whitelist_action)
        
        self.import_whitelist_action = QAction("Importar Whitelist", self)
        self.lists_menu.addAction(self.import_whitelist_action)

        self.exit_action = QAction("Sair", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.file_menu.addAction(self.exit_action)

        self.tools_menu = self.menu_bar.addMenu("Ferramentas")
        self.tools_history_menu = self.tools_menu.addMenu("Histórico")

        self.block_site_action = QAction("Bloquear Site", self)
        self.tools_menu.addAction(self.block_site_action)

        self.import_block_lists_action = QAction("Importar Listas de Bloqueio", self)
        self.tools_menu.addAction(self.import_block_lists_action)

        self.manage_blocked_sites_action = QAction("Gerenciar Sites Bloqueados", self)
        self.tools_menu.addAction(self.manage_blocked_sites_action)

        self.settings_action = QAction("Configurações", self)
        self.tools_menu.addAction(self.settings_action)

        self.limpar_historico_action = QAction("Limpar Histórico", self)
        self.tools_menu.addAction(self.limpar_historico_action)

        self.bookmarks_menu = self.menu_bar.addMenu("Favoritos")
        self.update_bookmarks_menu()

    def setup_signals(self):
        if self.tabs is None:
            raise RuntimeError("QTabWidget não está inicializado em setup_signals")
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_url_bar_on_tab_change)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.back_button.clicked.connect(self.back)
        self.forward_button.clicked.connect(self.forward)
        self.reload_button.clicked.connect(self.reload)
        self.home_button.clicked.connect(self.go_home)
        self.new_tab_button.clicked.connect(self.add_new_tab)
        self.new_private_tab_button.clicked.connect(self.add_new_private_tab)
        self.bookmark_button.clicked.connect(self.add_to_bookmarks)
        self.new_page_action.triggered.connect(self.nova_pagina)
        self.private_tab_action.triggered.connect(self.add_new_private_tab)
        self.exit_action.triggered.connect(self.close)
        self.limpar_historico_action.triggered.connect(self.limpar_historico)
        self.block_site_action.triggered.connect(self.block_site)
        self.import_block_lists_action.triggered.connect(self.import_block_lists)
        self.settings_action.triggered.connect(self.open_settings)
        self.manage_blocked_sites_action.triggered.connect(self.manage_blocked_sites)
        self.export_blocked_sites_action.triggered.connect(self.export_blocked_sites)
        self.import_blocked_sites_action.triggered.connect(self.import_blocked_sites)
        self.export_blocked_lists_action.triggered.connect(self.export_blocked_lists)
        self.import_blocked_lists_action.triggered.connect(self.import_blocked_lists)
        self.export_whitelist_action.triggered.connect(self.export_whitelist)
        self.import_whitelist_action.triggered.connect(self.import_whitelist)
        print("Sinais configurados em setup_signals")  # Log de depuração

    def load_bookmarks(self):
        try:
            if not os.access(self.bookmarks_file, os.R_OK | os.W_OK):
                print(f"Aviso: Permissões insuficientes para acessar {self.bookmarks_file}")
                return []
            if os.path.exists(self.bookmarks_file):
                with open(self.bookmarks_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [b for b in data if isinstance(b, dict) and "title" in b and "url" in b]
            return []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar favoritos: {e}")
            return []

    def save_bookmarks(self):
        try:
            if not os.access(os.path.dirname(self.bookmarks_file) or '.', os.W_OK):
                print(f"Aviso: Permissões insuficientes para salvar {self.bookmarks_file}")
                return
            with open(self.bookmarks_file, "w") as f:
                json.dump(self.bookmarks, f, indent=4)
        except IOError as e:
            print(f"Erro ao salvar favoritos: {e}")

    def load_blocked_sites(self):
        try:
            if not os.access(self.blocked_sites_file, os.R_OK | os.W_OK):
                print(f"Aviso: Permissões insuficientes para acessar {self.blocked_sites_file}")
                return []
            if os.path.exists(self.blocked_sites_file):
                with open(self.blocked_sites_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        normalized_urls = []
                        for url in data:
                            if isinstance(url, str):
                                normalized = self.normalize_domain(url)
                                if normalized:
                                    normalized_urls.append(normalized)
                                else:
                                    print(f"Aviso: URL inválida ignorada no arquivo de sites bloqueados: {url}")
                            else:
                                print(f"Aviso: Entrada inválida no arquivo de sites bloqueados: {url}")
                        return normalized_urls
            return []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar lista de sites bloqueados: {e}")
            return []

    def save_blocked_sites(self):
        try:
            if not os.access(os.path.dirname(self.blocked_sites_file) or '.', os.W_OK):
                print(f"Aviso: Permissões insuficientes para salvar {self.blocked_sites_file}")
                return
            with open(self.blocked_sites_file, "w") as f:
                json.dump(self.blocked_sites, f, indent=4)
            self.blocker.blocked_domains = self.blocked_sites
        except IOError as e:
            print(f"Erro ao salvar lista de sites bloqueados: {e}")

    def load_blocked_lists(self):
        try:
            if not os.access(self.blocked_lists_file, os.R_OK | os.W_OK):
                print(f"Aviso: Permissões insuficientes para acessar {self.blocked_lists_file}")
                return []
            if os.path.exists(self.blocked_lists_file):
                with open(self.blocked_lists_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [url for url in data if isinstance(url, str) and QUrl(url).isValid()]
            return []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar lista de fontes de bloqueio: {e}")
            return []

    def save_blocked_lists(self):
        try:
            if not os.access(os.path.dirname(self.blocked_lists_file) or '.', os.W_OK):
                print(f"Aviso: Permissões insuficientes para salvar {self.blocked_lists_file}")
                return
            with open(self.blocked_lists_file, "w") as f:
                json.dump(self.blocked_lists, f, indent=4)
        except IOError as e:
            print(f"Erro ao salvar lista de fontes de bloqueio: {e}")

    def load_whitelist(self):
        try:
            if not os.access(self.whitelist_file, os.R_OK | os.W_OK):
                print(f"Aviso: Permissões insuficientes para acessar {self.whitelist_file}")
                return []
            if os.path.exists(self.whitelist_file):
                with open(self.whitelist_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        normalized_urls = []
                        for url in data:
                            if isinstance(url, str):
                                normalized = self.normalize_domain(url)
                                if normalized:
                                    normalized_urls.append(normalized)
                                else:
                                    print(f"Aviso: URL inválida ignorada no arquivo de whitelist: {url}")
                            else:
                                print(f"Aviso: Entrada inválida no arquivo de whitelist: {url}")
                        return normalized_urls
            return []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar lista de permissões: {e}")
            return []

    def save_whitelist(self):
        try:
            if not os.access(os.path.dirname(self.whitelist_file) or '.', os.W_OK):
                print(f"Aviso: Permissões insuficientes para salvar {self.whitelist_file}")
                return
            with open(self.whitelist_file, "w") as f:
                json.dump(self.whitelist, f, indent=4)
            self.blocker.whitelist = self.whitelist
        except IOError as e:
            print(f"Erro ao salvar lista de permissões: {e}")

    def load_settings(self):
        default_settings = {
            "max_domains": 50000,
            "batch_size": 200,
            "validation_mode": "Rigorosa",
            "custom_validation_urls": [],
            "adblock_support": False,
            "retries": 3,
            "sleep_time": 5,
            "rejected_limit": 5,
            "whitelist_enabled": True,
            "save_mode": "Incremental"
        }
        try:
            if not os.path.exists(self.settings_file):
                print(f"Arquivo {self.settings_file} não existe. Criando com configurações padrão.")
                try:
                    with open(self.settings_file, "w") as f:
                        json.dump(default_settings, f, indent=4)
                except IOError as e:
                    print(f"Erro ao criar {self.settings_file}: {e}")
                    return default_settings
            if not os.access(self.settings_file, os.R_OK | os.W_OK):
                print(f"Aviso: Permissões insuficientes para acessar {self.settings_file}")
                return default_settings
            with open(self.settings_file, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                print(f"Erro: {self.settings_file} contém dados inválidos. Retornando configurações padrão.")
                return default_settings
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar configurações de {self.settings_file}: {e}")
            return default_settings

    def export_blocked_sites(self):
        print("Exportando lista de sites bloqueados")  # Log de depuração
        file_name, _ = QFileDialog.getSaveFileName(self, "Exportar Lista de Sites Bloqueados", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "w") as f:
                    json.dump(self.blocked_sites, f, indent=4)
                QMessageBox.information(self, "Exportação", "Lista de sites bloqueados exportada com sucesso.")
            except IOError as e:
                print(f"Erro ao exportar lista de sites bloqueados: {e}")
                QMessageBox.warning(self, "Erro", f"Falha ao exportar lista de sites bloqueados: {e}")

    def import_blocked_sites(self):
        print("Importando lista de sites bloqueados")  # Log de depuração
        file_name, _ = QFileDialog.getOpenFileName(self, "Importar Lista de Sites Bloqueados", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "r") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("O arquivo deve conter uma lista de domínios.")
                    normalized_urls = []
                    rejected_urls = []
                    for url in data:
                        if isinstance(url, str):
                            normalized = self.normalize_domain(url)
                            if normalized and normalized not in normalized_urls:
                                if self.settings.get("whitelist_enabled", True) and normalized in self.whitelist:
                                    rejected_urls.append(url)
                                    print(f"Aviso: Domínio na whitelist rejeitado: {url}")
                                    continue
                                normalized_urls.append(normalized)
                            else:
                                rejected_urls.append(url)
                                print(f"Aviso: URL inválida ou duplicada ignorada: {url}")
                        else:
                            rejected_urls.append(url)
                            print(f"Aviso: Entrada inválida ignorada: {url}")
                    self.blocked_sites.extend(normalized_urls)
                    self.save_blocked_sites()
                    self.update_blocked_domains()
                    QMessageBox.information(self, "Importação", f"{len(normalized_urls)} site(s) importado(s) com sucesso.")
                    if rejected_urls:
                        QMessageBox.warning(self, "Aviso", f"{len(rejected_urls)} domínio(s) rejeitado(s): {', '.join(rejected_urls[:5])}{'...' if len(rejected_urls) > 5 else ''}")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                print(f"Erro ao importar lista de sites bloqueados: {e}")
                QMessageBox.warning(self, "Erro", f"Falha ao importar lista de sites bloqueados: {e}")

    def export_blocked_lists(self):
        print("Exportando listas de bloqueio")  # Log de depuração
        file_name, _ = QFileDialog.getSaveFileName(self, "Exportar Listas de Bloqueio", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "w") as f:
                    json.dump(self.blocked_lists, f, indent=4)
                QMessageBox.information(self, "Exportação", "Listas de bloqueio exportadas com sucesso.")
            except IOError as e:
                print(f"Erro ao exportar listas de bloqueio: {e}")
                QMessageBox.warning(self, "Erro", f"Falha ao exportar listas de bloqueio: {e}")

    def import_blocked_lists(self):
        print("Importando listas de bloqueio")  # Log de depuração
        file_name, _ = QFileDialog.getOpenFileName(self, "Importar Listas de Bloqueio", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "r") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("O arquivo deve conter uma lista de URLs.")
                    normalized_urls = []
                    rejected_urls = []
                    for url in data:
                        if isinstance(url, str) and QUrl(url).isValid():
                            if url not in normalized_urls and url not in self.blocked_lists:
                                normalized_urls.append(url)
                            else:
                                rejected_urls.append(url)
                                print(f"Aviso: URL duplicada ou já existente ignorada: {url}")
                        else:
                            rejected_urls.append(url)
                            print(f"Aviso: URL inválida ignorada: {url}")
                    self.blocked_lists.extend(normalized_urls)
                    self.save_blocked_lists()
                    self.update_blocked_domains()
                    QMessageBox.information(self, "Importação", f"{len(normalized_urls)} lista(s) importada(s) com sucesso.")
                    if rejected_urls:
                        QMessageBox.warning(self, "Aviso", f"{len(rejected_urls)} URL(s) rejeitada(s): {', '.join(rejected_urls[:5])}{'...' if len(rejected_urls) > 5 else ''}")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                print(f"Erro ao importar listas de bloqueio: {e}")
                QMessageBox.warning(self, "Erro", f"Falha ao importar listas de bloqueio: {e}")

    def export_whitelist(self):
        print("Exportando whitelist")  # Log de depuração
        file_name, _ = QFileDialog.getSaveFileName(self, "Exportar Whitelist", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "w") as f:
                    json.dump(self.whitelist, f, indent=4)
                QMessageBox.information(self, "Exportação", "Whitelist exportada com sucesso.")
            except IOError as e:
                print(f"Erro ao exportar whitelist: {e}")
                QMessageBox.warning(self, "Erro", f"Falha ao exportar whitelist: {e}")

    def import_whitelist(self):
        print("Importando whitelist")  # Log de depuração
        file_name, _ = QFileDialog.getOpenFileName(self, "Importar Whitelist", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "r") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("O arquivo deve conter uma lista de domínios.")
                    normalized_urls = []
                    rejected_urls = []
                    for url in data:
                        if isinstance(url, str):
                            normalized = self.normalize_domain(url)
                            if normalized and normalized not in normalized_urls and normalized not in self.whitelist:
                                normalized_urls.append(normalized)
                            else:
                                rejected_urls.append(url)
                                print(f"Aviso: URL inválida ou duplicada ignorada: {url}")
                        else:
                            rejected_urls.append(url)
                            print(f"Aviso: Entrada inválida ignorada: {url}")
                    self.whitelist.extend(normalized_urls)
                    self.save_whitelist()
                    self.update_blocked_domains()
                    QMessageBox.information(self, "Importação", f"{len(normalized_urls)} site(s) importado(s) para a whitelist.")
                    if rejected_urls:
                        QMessageBox.warning(self, "Aviso", f"{len(rejected_urls)} domínio(s) rejeitado(s): {', '.join(rejected_urls[:5])}{'...' if len(rejected_urls) > 5 else ''}")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                print(f"Erro ao importar whitelist: {e}")
                QMessageBox.warning(self, "Erro", f"Falha ao importar whitelist: {e}")

    def open_settings(self):
        print("Abrindo diálogo de configurações")  # Log de depuração
        dialog = SettingsDialog(self.settings_file, self)
        dialog.exec()
        self.settings = self.load_settings()
        self.blocker.settings = self.settings

    def normalize_domain(self, domain):
        domain = domain.strip().lower()
        domain = re.sub(r'^https?://', '', domain)
        domain = domain.split('/')[0]
        if not domain or domain.startswith('localhost'):
            print(f"Aviso: Domínio inválido rejeitado no carregamento: {domain}")
            return None
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', domain):
            return domain
        if any(ord(c) > 127 for c in domain):
            try:
                domain = idna.encode(domain).decode('ascii')
            except idna.IDNAError:
                print(f"Aviso: Falha ao converter IDN no carregamento: {domain}")
                return None
        validation_mode = self.settings.get("validation_mode", "Rigorosa") if hasattr(self, 'settings') else "Rigorosa"
        if validation_mode == "Relaxada":
            return domain
        if re.match(r'^[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]*)*\.[a-z0-9]{1,}$', domain):
            return domain
        print(f"Aviso: Domínio inválido rejeitado no carregamento: {domain}")
        return None

    def import_block_lists(self):
        print("Abrindo diálogo de importação de listas de bloqueio")  # Log de depuração
        dialog = ImportBlockListsDialog(self.update_blocked_domains, self.blocked_sites, self.blocked_lists, self.blocked_sites_file, self.whitelist, self.settings, self)
        dialog.exec()

    def block_site(self):
        print("Abrindo diálogo para bloquear site")  # Log de depuração
        url, ok = QInputDialog.getText(self, "Bloquear Site", "Digite a URL do site a ser bloqueado (ex: https://example.com):")
        if ok and url:
            url = url.strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            normalized = self.normalize_domain(url)
            if not normalized:
                QMessageBox.warning(self, "URL Inválida", "Por favor, insira uma URL válida.")
                return
            if self.settings.get("whitelist_enabled", True) and normalized in self.whitelist:
                QMessageBox.warning(self, "Whitelist", f"O domínio {normalized} está na whitelist e não pode ser bloqueado.")
                return
            if normalized not in self.blocked_sites:
                self.blocked_sites.append(normalized)
                self.save_blocked_sites()
                QMessageBox.information(self, "Site Bloqueado", f"O site {url} foi adicionado à lista de bloqueio.")
            else:
                QMessageBox.information(self, "Site Já Bloqueado", f"O site {url} já está na lista de bloqueio.")

    def add_to_whitelist(self, domain):
        print(f"Adicionando {domain} à whitelist")  # Log de depuração
        if domain not in self.whitelist:
            self.whitelist.append(domain)
            self.save_whitelist()
            if domain in self.blocked_sites:
                self.blocked_sites.remove(domain)
                self.save_blocked_sites()

    def remove_from_whitelist(self, domain):
        print(f"Removendo {domain} da whitelist")  # Log de depuração
        if domain in self.whitelist:
            self.whitelist.remove(domain)
            self.save_whitelist()

    def manage_blocked_sites(self):
        print("Iniciando manage_blocked_sites")  # Log de depuração
        try:
            dialog = ManageBlockedSitesDialog(
                self.blocked_sites,
                self.blocked_lists,
                self.whitelist,
                self.remove_blocked_site,
                self.remove_blocked_list,
                self.add_to_whitelist,
                self.remove_from_whitelist,
                self
            )
            dialog.exec()
            print("Diálogo ManageBlockedSitesDialog fechado")  # Log de depuração
        except Exception as e:
            print(f"Erro ao abrir ManageBlockedSitesDialog: {e}")
            QMessageBox.warning(self, "Erro", f"Falha ao abrir Gerenciar Sites Bloqueados: {e}")

    def remove_blocked_site(self, url):
        print(f"Removendo site bloqueado: {url}")  # Log de depuração
        if url in self.blocked_sites:
            self.blocked_sites.remove(url)
            self.save_blocked_sites()
            QMessageBox.information(self, "Site Removido", f"O site {url} foi removido da lista de bloqueio.")

    def remove_blocked_list(self, url):
        print(f"Removendo lista bloqueada: {url}")  # Log de depuração
        if url in self.blocked_lists:
            self.blocked_lists.remove(url)
            self.save_blocked_lists()
            QMessageBox.information(self, "Lista Removida", f"A lista {url} foi removida.")
            self.update_blocked_domains()

    def update_blocked_domains(self):
        print("Atualizando domínios bloqueados")  # Log de depuração
        self.blocker.blocked_domains = self.blocked_sites
        self.blocker.whitelist = self.whitelist
        self.save_blocked_sites()
        self.save_blocked_lists()

    def go_home(self):
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            current_web_view.setUrl(QUrl("https://www.google.com"))

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
        print("Adicionando aos favoritos")  # Log de depuração
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
        if qurl is None or not isinstance(qurl, QUrl) or not qurl.isValid():
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
                try:
                    web_view.urlChanged.disconnect()
                    web_view.loadProgress.disconnect()
                    web_view.loadFinished.disconnect()
                    web_view.titleChanged.disconnect()
                    if web_view.page().profile() != self.private_profile:
                        try:
                            web_view.urlChanged.disconnect(self.add_to_history)
                        except TypeError:
                            pass
                except Exception as e:
                    print(f"Erro ao desconectar sinais da aba {index}: {e}")
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
            current_web_view.reload()

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
        self.save_blocked_lists()
        self.save_whitelist()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QMenuBar {
            background-color: #ffffff;
            color: #333333;
            font-size: 12px;
        }
        QMenuBar::item {
            background-color: #ffffff;
            padding: 5px 10px;
        }
        QMenuBar::item:selected {
            background-color: #e0e0e0;
        }
        QMenu {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
        }
        QMenu::item {
            padding: 5px 20px;
        }
        QMenu::item:selected {
            background-color: #28a745;
            color: #ffffff;
        }
        QPushButton {
            background-color: #28a745;
            color: #ffffff;
            border: none;
            border-radius: 5px;
            padding: 5px;
            min-width: 30px;
            min-height: 30px;
        }
        QPushButton:hover {
            background-color: #218838;
        }
        QPushButton:pressed {
            background-color: #1e7e34;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
            border-radius: 5px;
            padding: 5px;
            font-size: 12px;
        }
        QTabWidget::pane {
            border: 1px solid #cccccc;
            background-color: #f5f5f5;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            color: #333333;
            padding: 8px 15px;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #28a745;
            color: #ffffff;
            font-weight: bold;
        }
        QTabBar::tab:hover {
            background-color: #d0d0d0;
        }
        QProgressBar {
            background-color: #e0e0e0;
            border: 1px solid #cccccc;
            border-radius: 5px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #28a745;
            border-radius: 5px;
        }
        QDialog {
            background-color: #f5f5f5;
            color: #333333;
        }
        QListWidget {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
        }
        QListWidget::item:selected {
            background-color: #28a745;
            color: #ffffff;
        }
        QMessageBox {
            background-color: #f5f5f5;
            color: #333333;
        }
        QInputDialog {
            background-color: #f5f5f5;
            color: #333333;
        }
        QFileDialog {
            background-color: #f5f5f5;
            color: #333333;
        }
        QLabel {
            color: #333333;
        }
    """)
    browser = Browser()
    browser.show()
    sys.exit(app.exec())
