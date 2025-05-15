import sys, os
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QStackedWidget, QFileDialog, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QTranslator, QCoreApplication, QTimer, pyqtSlot
#sys.stdout = open(os.devnull, 'w')
from qfluentwidgets import setThemeColor, TransparentToolButton, FluentIcon, PushSettingCard, isDarkTheme, SettingCard, MessageBox, FluentTranslator, IndeterminateProgressBar, HeaderCardWidget, BodyLabel, IconWidget, InfoBarIcon, PushButton, SubtitleLabel, ComboBoxSettingCard, OptionsSettingCard, HyperlinkCard, ScrollArea, InfoBar, InfoBarPosition, StrongBodyLabel, Flyout, FlyoutAnimationType, TransparentPushButton
from winrt.windows.ui.viewmanagement import UISettings, UIColorType
from resource.config import cfg, TranslationPackage
from resource.argos_utils import update_package, update_device
from resource.translator import FileTranslator
import shutil
import traceback, gc
import tempfile
from ctranslate2 import get_cuda_device_count
import glob
from pathlib import Path

def get_lib_paths():
    if getattr(sys, 'frozen', False):  # Running inside PyInstaller
        base_dir = os.path.join(sys.prefix)
    else:  # Running inside a virtual environment
        base_dir = os.path.join(sys.prefix, "Lib", "site-packages")

    nvidia_base_libs = os.path.join(base_dir, "nvidia")
    cuda_libs = os.path.join(nvidia_base_libs, "cuda_runtime", "bin")
    cublas_libs = os.path.join(nvidia_base_libs, "cublas", "bin")
    cudnn_libs = os.path.join(nvidia_base_libs, "cudnn", "bin")

    return [cuda_libs, cublas_libs, cudnn_libs]


for dll_path in get_lib_paths():
    if os.path.exists(dll_path):
        os.environ["PATH"] = dll_path + os.pathsep + os.environ["PATH"]

if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    base_dir = os.path.dirname(sys.executable)  # Points to build/
    res_dir = os.path.join(sys.prefix)
else:
    # Running as a script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    res_dir = base_dir

class FileLabel(QLabel):
    fileSelected = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_text = "Ready for translation"
        self.current_file_label = None  # Will store the current QLabel showing file and status
        self.setText(self.update_text_color())
        self.setStyleSheet('''
            QLabel{
                border: 3px dashed #aaa;
            }
        ''')
        self.setAcceptDrops(True)
        self.deleted = False


    def create_text(self, color, lang):
        font_size = "16px"
        if lang == 'RUSSIAN':
            text = f'''
            <p style="text-align: center; font-size: {font_size}; color: {color};">
                <br><br> Перетащите сюда любой PDF, EPUB, TXT или DOCX файл <br>
                <br>или<br><br>
                <a href="" style="color: {color};"><strong>Нажмите в любом месте для выбора</strong></a>
                <br>
            </p>
        '''
        else:
            text = f'''
            <p style="text-align: center; font-size: {font_size}; color: {color};">
                <br><br> Drag&Drop any PDF, EPUB, TXT or DOCX file<br>
                <br>or<br><br>
                <a href="" style="color: {color};"><strong>Click anywhere to browse</strong></a>
                <br>
            </p>
        '''
        return text

    def update_text_color(self):
        color = 'white' if isDarkTheme() else 'black'
        lang = cfg.get(cfg.language).name
        return self.create_text(color, lang)

    def update_theme(self):
        if not self.deleted:
            self.setText(self.update_text_color())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_file_dialog()

    def open_file_dialog(self):
        initial_dir = self.main_window.last_directory if self.main_window.last_directory else ""

        self.file_path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("MainWindow", "Select file"),
            initial_dir,
            QCoreApplication.translate("MainWindow",
                "Text files (*.pdf *.epub *.docx *.txt);;"
                "All Files (*)")
        )
        if self.file_path:
            self.main_window.last_directory = os.path.dirname(self.file_path)
            if self.is_document(self.file_path):
                self.fileSelected.emit(self.file_path)
                self.file_accepted(self.file_path)
            elif self.is_not_supported_document(self.file_path):
                InfoBar.error(
                    title=QCoreApplication.translate("MainWindow", "Error"),
                    content=QCoreApplication.translate("MainWindow", "This file format is not fully supported. Please convert it to .docx and try again"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,
                    duration=4000,
                    parent=window
                )
            else:
                InfoBar.error(
                    title=QCoreApplication.translate("MainWindow", "Error"),
                    content=QCoreApplication.translate("MainWindow", "Dropped file is not supported"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,
                    duration=4000,
                    parent=window
                )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                self.file_path = url.toLocalFile()
                if self.is_document(self.file_path):
                    self.main_window.last_directory = os.path.dirname(self.file_path)

                    self.fileSelected.emit(self.file_path)
                    self.file_accepted(self.file_path)
                elif self.is_not_supported_document(self.file_path):
                    InfoBar.error(
                        title=QCoreApplication.translate("MainWindow", "Error"),
                        content=QCoreApplication.translate("MainWindow", "This file format is not fully supported. Please convert it to .docx and try again"),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM,
                        duration=4000,
                        parent=window
                    )
                else:
                    InfoBar.error(
                        title=QCoreApplication.translate("MainWindow", "Error"),
                        content=QCoreApplication.translate("MainWindow", "Dropped file is not supported"),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM,
                        duration=4000,
                        parent=window
                    )

    def update_status_text(self, new_text):
        """Update the status text and refresh the display"""
        self.status_text = new_text
        if self.current_file_label:  # Only update if we have an active file label
            self.current_file_label.setText(f"<center><strong>{os.path.basename(self.current_file_label.file_path)}</strong><br><br>{new_text}</center>")

    def file_accepted(self, file_path):
        self.deleted = True
        self.setStyleSheet("")
        
        # Create a styled label to replace this one
        self.current_file_label = QLabel(f"<center><b>{os.path.basename(file_path)}</b><br><br>{self.status_text}</center>")
        self.current_file_label.file_path = file_path  # Store the path as an attribute
        self.current_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Apply theme-appropriate styling
        color = 'white' if isDarkTheme() else 'black'
        self.current_file_label.setStyleSheet(f'''
            QLabel {{
                color: {color};
                font-size: 16px;
                padding: 20px;
            }}
        ''')
        
        # Get the parent layout and replace this widget
        parent = self.parentWidget()
        if parent:
            layout = parent.layout()
            if layout:
                # Replace the widget at index 0
                layout.replaceWidget(self, self.current_file_label)
                self.current_file_label.show()  # Ensure the new label is shown
                self.deleteLater()  # Delete the old FileLabel widget

        self.main_window.back_button.show()
        QTimer.singleShot(400, lambda: self.update_status_text("Translating..."))
        QTimer.singleShot(400, lambda: self.main_window.start_translation_process(file_path))
              

    def is_document(self, file_path):
        file_extensions = ['.pdf', '.epub', '.docx', '.txt']
        _, ext = os.path.splitext(file_path)
        return ext.lower() in file_extensions

    def is_not_supported_document(self, file_path):
        file_extensions = ['.doc', '.odt', '.rtf']
        _, ext = os.path.splitext(file_path)
        return ext.lower() in file_extensions

class MainWindow(QMainWindow):
    theme_changed = pyqtSignal()
    device_changed = pyqtSignal()
    package_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "celosia"))
        self.setWindowIcon(QIcon(os.path.join(res_dir, "resource", "assets", "icon.ico")))
        self.setGeometry(100,100,999,446)
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.main_layout()
        self.settings_layout()
        self.setup_theme()
        self.center()
        self.model = None
        self.last_directory = ""
        self.setAcceptDrops(True)

        self.theme_changed.connect(self.update_theme)
        self.device_changed.connect(lambda: update_device(self))
        self.package_changed.connect(lambda: update_package(self))

        self.file_translator = FileTranslator(self, cfg)

        QTimer.singleShot(100, self.init_check)

    def init_check(self):
        if (get_cuda_device_count() == 0) and ((cfg.get(cfg.device).value == 'cuda')):
            InfoBar.info(
                title=(QCoreApplication.translate("MainWindow", "Information")),
                content=(QCoreApplication.translate("MainWindow", "<b>No NVIDIA graphics card detected</b>. Application will run on CPU.")),
                orient=Qt.Orientation.Horizontal,
                isClosable=False,
                position=InfoBarPosition.BOTTOM,
                duration=4000,
                parent=window
            )
            cfg.set(cfg.device, 'cpu')

    def setup_theme(self):
        main_color_hex = self.get_main_color_hex()
        setThemeColor(main_color_hex)
        if isDarkTheme():
            theme_stylesheet = """
                QWidget {
                    background-color: #1e1e1e;  /* Dark background */
                    border: none;
                }
                QFrame {
                    background-color: transparent;
                    border: none;
                }
            """
        else:
            theme_stylesheet = """
                QWidget {
                    background-color: #f0f0f0;  /* Light background */
                    border: none;
                }
                QFrame {
                    background-color: transparent;
                    border: none;
                }
            """
        self.filepicker.update_theme()
        QApplication.instance().setStyleSheet(theme_stylesheet)

    def get_main_color_hex(self):
        color = UISettings().get_color_value(UIColorType.ACCENT)
        return f'#{int((color.r)):02x}{int((color.g)):02x}{int((color.b )):02x}'

    def update_theme(self):
        self.setup_theme()

    def restartinfo(self):
        InfoBar.warning(
            title=(QCoreApplication.translate("MainWindow", "Success")),
            content=(QCoreApplication.translate("MainWindow", "Setting takes effect after restart")),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self.settings_win
        )

    def return_to_filepicker(self):
        if hasattr(self, 'progressbar'):
            self.progressbar.stop()
        # Get the main widget (index 0 in stacked widget)
        main_widget = self.stacked_widget.widget(0)
        
        # Find the layout in this widget
        main_layout = main_widget.layout()
        
        # Remove all widgets from the layout except the last one (which contains the settings buttons)
        item = main_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        
        # Recreate the filepicker
        self.filepicker = FileLabel(self)
        main_layout.insertWidget(0, self.filepicker)
        # Hide the back button
        self.back_button.hide()

    def center(self):
        screen_geometry = self.screen().availableGeometry()
        window_geometry = self.geometry()

        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2

        self.move(x, y)

    def update_argos_remove_button_state(self,enabled):
        if hasattr(self, 'card_deleteargosmodel'):
            self.card_deleteargosmodel.button.setEnabled(enabled)

    def main_layout(self):
        main_layout = QVBoxLayout()
        self.filepicker = FileLabel(self)
        main_layout.addWidget(self.filepicker)

        self.settings_button = TransparentToolButton(FluentIcon.SETTING)

        self.back_button = TransparentToolButton(FluentIcon.LEFT_ARROW)
        self.back_button.hide()


        settings_layout = QHBoxLayout()
        settings_layout.addWidget(self.settings_button)
        settings_layout.addWidget(self.back_button)
        settings_layout.addStretch()
        settings_layout.setContentsMargins(5, 5, 5, 5)

        self.progressbar = IndeterminateProgressBar(start=False)
        main_layout.addWidget(self.progressbar)

        main_layout.addLayout(settings_layout)

        #connect
        self.settings_button.clicked.connect(self.show_settings_page)
        self.back_button.clicked.connect(self.return_to_filepicker)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.stacked_widget.addWidget(main_widget)

    def settings_layout(self):
        settings_layout = QVBoxLayout()

        back_button_layout = QHBoxLayout()

        back_button = TransparentToolButton(FluentIcon.LEFT_ARROW)
        back_button.clicked.connect(self.show_main_page)

        back_button_layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignTop)
        back_button_layout.setContentsMargins(5, 5, 5, 5)

        settings_layout.addLayout(back_button_layout)

        self.settings_title = SubtitleLabel(QCoreApplication.translate("MainWindow", "Settings"))
        self.settings_title.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))

        back_button_layout.addWidget(self.settings_title, alignment=Qt.AlignmentFlag.AlignTop)

        card_layout = QVBoxLayout()
        self.devices_title = StrongBodyLabel(QCoreApplication.translate("MainWindow", "Devices"))
        self.devices_title.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))
        card_layout.addWidget(self.devices_title, alignment=Qt.AlignmentFlag.AlignTop)

        self.card_setdevice = ComboBoxSettingCard(
            configItem=cfg.device,
            icon=FluentIcon.DEVELOPER_TOOLS,
            title=QCoreApplication.translate("MainWindow","Device"),
            content=QCoreApplication.translate("MainWindow", "Select a device to use. Cuda will utilize GPU."),
            texts=['cpu', 'cuda']
        )

        card_layout.addWidget(self.card_setdevice, alignment=Qt.AlignmentFlag.AlignTop)

        if get_cuda_device_count() == 0:
            self.card_setdevice.hide()
            self.devices_title.hide()
            if cfg.get(cfg.device).value == 'cuda':
                cfg.set(cfg.device, 'cpu')

        cfg.device.valueChanged.connect(self.device_changed.emit)

        self.modelsins_title = StrongBodyLabel(QCoreApplication.translate("MainWindow", "Model management"))
        self.modelsins_title.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))
        card_layout.addSpacing(20)
        card_layout.addWidget(self.modelsins_title, alignment=Qt.AlignmentFlag.AlignTop)

        self.card_settlpackage = ComboBoxSettingCard(
            configItem=cfg.package,
            icon=FluentIcon.CLOUD_DOWNLOAD,
            title=QCoreApplication.translate("MainWindow","Argos Translate package"),
            content=QCoreApplication.translate("MainWindow", "Change translation package"),
            texts=[
                "None", "sq_en", "ar_en", "az_en", "eu_en", "bn_en", "bg_en", "ca_en", "zh_tw_en", "zh_en",
                "cs_en", "da_en", "nl_en", "en_sq", "en_ar", "en_az", "en_eu", "en_bn", "en_bg",
                "en_ca", "en_zh", "en_zh_tw", "en_cs", "en_da", "en_nl", "en_eo", "en_et", "en_fi",
                "en_fr", "en_gl", "en_de", "en_el", "en_he", "en_hi", "en_hu", "en_id", "en_ga",
                "en_it", "en_ja", "en_ko", "en_lv", "en_lt", "en_ms", "en_no", "en_fa", "en_pl",
                "en_pt", "en_pt_br", "en_ro", "en_ru", "en_sk", "en_sl", "en_es", "en_sv", "en_tl",
                "en_th", "en_tr", "en_uk", "en_ur", "eo_en", "et_en", "fi_en", "fr_en", "gl_en",
                "de_en", "el_en", "he_en", "hi_en", "hu_en", "id_en", "ga_en", "it_en", "ja_en",
                "ko_en", "lv_en", "lt_en", "ms_en", "no_en", "fa_en", "pl_en", "pt_br_en", "pt_en",
                "pt_es", "ro_en", "ru_en", "sk_en", "sl_en", "es_en", "es_pt", "sv_en", "tl_en",
                "th_en", "tr_en", "uk_en", "ur_en"
            ]
        )

        card_layout.addWidget(self.card_settlpackage, alignment=Qt.AlignmentFlag.AlignTop)
        cfg.package.valueChanged.connect(self.package_changed.emit)

        self.lang_widget = QWidget()
        self.lang_layout = QHBoxLayout()
        self.lang_widget.setLayout(self.lang_layout)
        self.lang_layout.addStretch()
        card_layout.addWidget(self.lang_widget)
        self.check_packages()

        self.card_deleteargosmodel = PushSettingCard(
            text=QCoreApplication.translate("MainWindow","Remove"),
            icon=FluentIcon.BROOM,
            title=QCoreApplication.translate("MainWindow","Remove Argos Translate package"),
            content=QCoreApplication.translate("MainWindow", "Delete currently selected translation package. Will be removed: <b>{}</b>").format(cfg.get(cfg.package).value),
        )

        card_layout.addWidget(self.card_deleteargosmodel, alignment=Qt.AlignmentFlag.AlignTop)
        self.card_deleteargosmodel.clicked.connect(self.packageremover)
        if ((cfg.get(cfg.package).value == 'None')):
            self.card_deleteargosmodel.button.setDisabled(True)

        self.miscellaneous_title = StrongBodyLabel(QCoreApplication.translate("MainWindow", "Miscellaneous"))
        self.miscellaneous_title.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))
        card_layout.addSpacing(20)
        card_layout.addWidget(self.miscellaneous_title, alignment=Qt.AlignmentFlag.AlignTop)

        self.card_setlanguage = ComboBoxSettingCard(
            configItem=cfg.language,
            icon=FluentIcon.LANGUAGE,
            title=QCoreApplication.translate("MainWindow","Language"),
            content=QCoreApplication.translate("MainWindow", "Change UI language"),
            texts=["English", "Русский"]
        )

        card_layout.addWidget(self.card_setlanguage, alignment=Qt.AlignmentFlag.AlignTop)
        cfg.language.valueChanged.connect(self.restartinfo)

        self.card_theme = OptionsSettingCard(
            cfg.themeMode,
            FluentIcon.BRUSH,
            QCoreApplication.translate("MainWindow","Application theme"),
            QCoreApplication.translate("MainWindow", "Adjust how the application looks"),
            [QCoreApplication.translate("MainWindow","Light"), QCoreApplication.translate("MainWindow","Dark"), QCoreApplication.translate("MainWindow","Follow System Settings")]
        )

        card_layout.addWidget(self.card_theme, alignment=Qt.AlignmentFlag.AlignTop)
        self.card_theme.optionChanged.connect(self.theme_changed.emit)

        self.card_zoom = OptionsSettingCard(
            cfg.dpiScale,
            FluentIcon.ZOOM,
            QCoreApplication.translate("MainWindow","Interface zoom"),
            QCoreApplication.translate("MainWindow","Change the size of widgets and fonts"),
            texts=[
                "100%", "125%", "150%", "175%", "200%",
                QCoreApplication.translate("MainWindow","Follow System Settings")
            ]
        )

        card_layout.addWidget(self.card_zoom, alignment=Qt.AlignmentFlag.AlignTop)
        cfg.dpiScale.valueChanged.connect(self.restartinfo)

        self.card_ab = HyperlinkCard(
            url="https://github.com/icosane/celosia",
            text="Github",
            icon=FluentIcon.INFO,
            title=QCoreApplication.translate("MainWindow", "About"),
            content=QCoreApplication.translate("MainWindow", "Translate PDF and EPUB files locally")
        )
        card_layout.addWidget(self.card_ab,  alignment=Qt.AlignmentFlag.AlignTop )

        self.scroll_area = ScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.card_widget = QWidget()
        self.card_widget.setLayout(card_layout)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.card_widget)
        settings_layout.addWidget(self.scroll_area)

        self.download_progressbar = IndeterminateProgressBar(start=False)
        settings_layout.addWidget(self.download_progressbar )

        settings_widget = QWidget()
        settings_widget.setLayout(settings_layout)

        self.stacked_widget.addWidget(settings_widget)

    def show_settings_page(self):
        self.stacked_widget.setCurrentIndex(1)  # Switch to the settings page

    def show_main_page(self):
        self.stacked_widget.setCurrentIndex(0)  # Switch back to the main page

    def check_packages(self):

        languages = {
            'en_ru': 'English → Russian',
            'ru_en': 'Russian → English',
            'de_en': 'German → English',
            'fr_en': 'French → English',
            'it_en': 'Italian → English',
            'ja_en': 'Japanese → English',
            'sq_en': 'Albanian → English',
            'ar_en': 'Arabic → English',
            'az_en': 'Azerbaijani → English',
            'eu_en': 'Basque → English',
            'bn_en': 'Bengali → English',
            'bg_en': 'Bulgarian → English',
            'ca_en': 'Catalan → English',
            'zt_en': 'Chinese (Mandarin) → English',
            'zh_en': 'Chinese → English',
            'cs_en': 'Czech → English',
            'da_en': 'Danish → English',
            'nl_en': 'Dutch → English',
            'en_sq': 'English → Albanian',
            'en_ar': 'English → Arabic',
            'en_az': 'English → Azerbaijani',
            'en_eu': 'English → Basque',
            'en_bn': 'English → Bengali',
            'en_bg': 'English → Bulgarian',
            'en_ca': 'English → Catalan',
            'en_zh': 'English → Chinese',
            'en_zt': 'English → Chinese (Mandarin)',
            'en_cs': 'English → Czech',
            'en_da': 'English → Danish',
            'en_nl': 'English → Dutch',
            'en_eo': 'English → Esperanto',
            'en_et': 'English → Estonian',
            'en_fi': 'English → Finnish',
            'en_fr': 'English → French',
            'en_gl': 'English → Galician',
            'en_de': 'English → German',
            'en_el': 'English → Greek',
            'en_he': 'English → Hebrew',
            'en_hi': 'English → Hindi',
            'en_hu': 'English → Hungarian',
            'en_id': 'English → Indonesian',
            'en_ga': 'English → Irish',
            'en_it': 'English → Italian',
            'en_ja': 'English → Japanese',
            'en_ko': 'English → Korean',
            'en_lv': 'English → Latvian',
            'en_lt': 'English → Lithuanian',
            'en_ms': 'English → Malay',
            'en_nb': 'English → Norwegian Bokmal',
            'en_fa': 'English → Persian',
            'en_pl': 'English → Polish',
            'en_pt': 'English → Portuguese',
            'en_pb': 'English → Portuguese (Brazil)',
            'en_ro': 'English → Romanian',
            'en_sk': 'English → Slovak',
            'en_sl': 'English → Slovenian',
            'en_es': 'English → Spanish',
            'en_sv': 'English → Swedish',
            'en_tl': 'English → Tagalog',
            'en_th': 'English → Thai',
            'en_tr': 'English → Turkish',
            'en_uk': 'English → Ukrainian',
            'en_ur': 'English → Urdu',
            'eo_en': 'Esperanto → English',
            'et_en': 'Estonian → English',
            'fi_en': 'Finnish → English',
            'gl_en': 'Galician → English',
            'el_en': 'Greek → English',
            'he_en': 'Hebrew → English',
            'hi_en': 'Hindi → English',
            'hu_en': 'Hungarian → English',
            'id_en': 'Indonesian → English',
            'ga_en': 'Irish → English',
            'lv_en': 'Latvian → English',
            'lt_en': 'Lithuanian → English',
            'ms_en': 'Malay → English',
            'nb_en': 'Norwegian Bokmal → English',
            'fa_en': 'Persian → English',
            'pl_en': 'Polish → English',
            'pb_en': 'Portuguese (Brazil) → English',
            'pt_en': 'Portuguese → English',
            'es_pt': 'Spanish → Portuguese',
            'ro_en': 'Romanian → English',
            'sk_en': 'Slovak → English',
            'sl_en': 'Slovenian → Spanish',
            'es_en': 'Spanish → English',
            'sv_en': 'Swedish → English',
            'tl_en': 'Tagalog → English',
            'th_en': 'Thai → English',
            'tr_en': 'Turkish → English',
            'uk_en': 'Ukrainian → English',
            'ur_en': 'Urdu → English'
        }
        
        translation_mapping = {
            'en_ru': TranslationPackage.EN_TO_RU,
            'ru_en': TranslationPackage.RU_TO_EN,
            'de_en': TranslationPackage.DE_TO_EN,
            'fr_en': TranslationPackage.FR_TO_EN,
            'it_en': TranslationPackage.IT_TO_EN,
            'ja_en': TranslationPackage.JA_TO_EN,
            'zh_en': TranslationPackage.ZH_TO_EN,
            'sq_en': TranslationPackage.SQ_TO_EN,
            'ar_en': TranslationPackage.AR_TO_EN,
            'az_en': TranslationPackage.AZ_TO_EN,
            'eu_en': TranslationPackage.EU_TO_EN,
            'bn_en': TranslationPackage.BN_TO_EN,
            'bg_en': TranslationPackage.BG_TO_EN,
            'ca_en': TranslationPackage.CA_TO_EN,
            'zt_en': TranslationPackage.ZT_TO_EN,
            'cs_en': TranslationPackage.CS_TO_EN,
            'da_en': TranslationPackage.DA_TO_EN,
            'nl_en': TranslationPackage.NL_TO_EN,
            'en_sq': TranslationPackage.EN_TO_SQ,
            'en_ar': TranslationPackage.EN_TO_AR,
            'en_az': TranslationPackage.EN_TO_AZ,
            'en_eu': TranslationPackage.EN_TO_EU,
            'en_bn': TranslationPackage.EN_TO_BN,
            'en_bg': TranslationPackage.EN_TO_BG,
            'en_ca': TranslationPackage.EN_TO_CA,
            'en_zh': TranslationPackage.EN_TO_ZH,
            'en_zt': TranslationPackage.EN_TO_ZT,
            'en_cs': TranslationPackage.EN_TO_CS,
            'en_da': TranslationPackage.EN_TO_DA,
            'en_nl': TranslationPackage.EN_TO_NL,
            'en_eo': TranslationPackage.EN_TO_EO,
            'en_et': TranslationPackage.EN_TO_ET,
            'en_fi': TranslationPackage.EN_TO_FI,
            'en_fr': TranslationPackage.EN_TO_FR,
            'en_gl': TranslationPackage.EN_TO_GL,
            'en_de': TranslationPackage.EN_TO_DE,
            'en_el': TranslationPackage.EN_TO_EL,
            'en_he': TranslationPackage.EN_TO_HE,
            'en_hi': TranslationPackage.EN_TO_HI,
            'en_hu': TranslationPackage.EN_TO_HU,
            'en_id': TranslationPackage.EN_TO_ID,
            'en_ga': TranslationPackage.EN_TO_GA,
            'en_it': TranslationPackage.EN_TO_IT,
            'en_ja': TranslationPackage.EN_TO_JA,
            'en_ko': TranslationPackage.EN_TO_KO,
            'en_lv': TranslationPackage.EN_TO_LV,
            'en_lt': TranslationPackage.EN_TO_LT,
            'en_ms': TranslationPackage.EN_TO_MS,
            'en_nb': TranslationPackage.EN_TO_NB,
            'en_fa': TranslationPackage.EN_TO_FA,
            'en_pl': TranslationPackage.EN_TO_PL,
            'en_pt': TranslationPackage.EN_TO_PT,
            'en_pb': TranslationPackage.EN_TO_PB,
            'en_ro': TranslationPackage.EN_TO_RO,
            'en_sk': TranslationPackage.EN_TO_SK,
            'en_sl': TranslationPackage.EN_TO_SL,
            'en_es': TranslationPackage.EN_TO_ES,
            'en_sv': TranslationPackage.EN_TO_SV,
            'en_tl': TranslationPackage.EN_TO_TL,
            'en_th': TranslationPackage.EN_TO_TH,
            'en_tr': TranslationPackage.EN_TO_TR,
            'en_uk': TranslationPackage.EN_TO_UK,
            'en_ur': TranslationPackage.EN_TO_UR,
            'eo_en': TranslationPackage.EO_TO_EN,
            'et_en': TranslationPackage.ET_TO_EN,
            'fi_en': TranslationPackage.FI_TO_EN,
            'gl_en': TranslationPackage.GL_TO_EN,
            'el_en': TranslationPackage.EL_TO_EN,
            'he_en': TranslationPackage.HE_TO_EN,
            'hi_en': TranslationPackage.HI_TO_EN,
            'hu_en': TranslationPackage.HU_TO_EN,
            'id_en': TranslationPackage.ID_TO_EN,
            'ga_en': TranslationPackage.GA_TO_EN,
            'lv_en': TranslationPackage.LV_TO_EN,
            'lt_en': TranslationPackage.LT_TO_EN,
            'ms_en': TranslationPackage.MS_TO_EN,
            'nb_en': TranslationPackage.NB_TO_EN,
            'fa_en': TranslationPackage.FA_TO_EN,
            'pl_en': TranslationPackage.PL_TO_EN,
            'pb_en': TranslationPackage.PB_TO_EN,
            'pt_en': TranslationPackage.PT_TO_EN,
            'es_pt': TranslationPackage.ES_TO_PT,
            'ro_en': TranslationPackage.RO_TO_EN,
            'sk_en': TranslationPackage.SK_TO_EN,
            'sl_en': TranslationPackage.SL_TO_EN,
            'es_en': TranslationPackage.ES_TO_EN,
            'sv_en': TranslationPackage.SV_TO_EN,
            'tl_en': TranslationPackage.TL_TO_EN,
            'th_en': TranslationPackage.TH_TO_EN,
            'tr_en': TranslationPackage.TR_TO_EN,
            'uk_en': TranslationPackage.UK_TO_EN,
            'ur_en': TranslationPackage.UR_TO_EN
        }

        for i in reversed(range(self.lang_layout.count())): 
            widget = self.lang_layout.itemAt(i).widget()
            if widget and widget.parent() is not None:
                widget.deleteLater()

        available_languages = []
        for language_pair, name in languages.items():
            package_patterns = [
                os.path.join(
                    base_dir,
                    "models/argostranslate/data/argos-translate/packages",
                    f"translate-{language_pair}-*"
                ),
                os.path.join(
                    base_dir,
                    "models/argostranslate/data/argos-translate/packages",
                    f"{language_pair}"
                )
            ]
            # Check if any pattern exists
            found = False
            for pattern in package_patterns:
                if any(Path(p).is_dir() for p in glob.glob(pattern)):
                    found = True
                    break
            if found:
                available_languages.append((language_pair, name))
        # Create buttons for available languages
        for code, name in available_languages:
            lang_button = TransparentPushButton(name)
            lang_button.clicked.connect(lambda _, c=code: self.card_settlpackage.setValue(translation_mapping[c]))
            self.lang_layout.addWidget(lang_button, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Show/hide layout based on whether there are available languages
        self.lang_widget.setVisible(len(available_languages) > 0)


    def packageremover(self):
        language_pair = cfg.get(cfg.package).value

        package_patterns = [
            os.path.join(
                base_dir,
                "models/argostranslate/data/argos-translate/packages",
                f"translate-{language_pair}-*"
            ),
            os.path.join(
                base_dir,
                "models/argostranslate/data/argos-translate/packages",
                f"{language_pair}"
            )
        ]


        # Remove .argosmodel file
        model_file = os.path.join(
            base_dir,
            "models/argostranslate/cache/argos-translate/downloads",
            f"translate-{language_pair}.argosmodel"
        )

        try:
            # Remove matching package directories
            removed_dirs = False
            for pattern in package_patterns:
                for dir_path in glob.glob(pattern):
                    if os.path.isdir(dir_path):
                        shutil.rmtree(dir_path)
                        removed_dirs = True

            # Remove model file if exists
            removed_file = False
            if os.path.exists(model_file):
                os.remove(model_file)
                removed_file = True

            # Only update config if we actually removed something
            if removed_dirs or removed_file:
                cfg.set(cfg.package, 'None')
                self.check_packages()

                InfoBar.success(
                    title=QCoreApplication.translate("MainWindow", "Success"),
                    content=QCoreApplication.translate("MainWindow", "Translation package removed successfully"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.warning(
                    title=QCoreApplication.translate("MainWindow", "Warning"),
                    content=QCoreApplication.translate("MainWindow", "No translation package found to remove"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )

        except Exception as e:
            InfoBar.error(
                title=QCoreApplication.translate("MainWindow", "Error"),
                content=QCoreApplication.translate("MainWindow", f"Failed to remove translation package: {str(e)}"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )

    def closeEvent(self, event):
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            print(f"Error clearing CUDA cache: {e}")

        for widget in QApplication.topLevelWidgets():
            widget.close()

        super().closeEvent(event)

    @pyqtSlot(str)
    def start_translation_process(self, file_path):
        """Delegate to srt translator"""
        self.file_translator.start_translation_process(file_path)

    def handle_translation_save_path(self, default_name, translated_content):
        initial_dir = self.last_directory if self.last_directory else ""
        default_name = os.path.join(initial_dir, os.path.basename(default_name))


        file_path, _ = QFileDialog.getSaveFileName(
            self,
            QCoreApplication.translate('MainWindow',"Save Translated File"),
            default_name,
            QCoreApplication.translate('MainWindow',"All Files (*)")
        )

        if hasattr(self.file_translator, 'translation_worker'):
            if file_path:
                self.last_directory = os.path.dirname(file_path)
                self.file_translator.translation_worker.save_path = file_path
                self.file_translator.translation_worker.translated_content = translated_content
            else:
                self.file_translator.translation_worker.save_path = ""
                self.file_translator.translation_worker.abort()
                self.progressbar.stop()
                self.return_to_filepicker()

    def on_translation_done(self, result, success):
        self.progressbar.stop()

        if success:
            self.return_to_filepicker()
            InfoBar.success(
                title=QCoreApplication.translate('MainWindow',"Success"),
                content=QCoreApplication.translate('MainWindow', "Translation saved to <b>{}</b>").format(result),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,
                duration=4000,
                parent=self
            )
        elif result:  # Error message
            self.return_to_filepicker()
            InfoBar.error(
                title=QCoreApplication.translate('MainWindow',"Error"),
                content=result,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,
                duration=4000,
                parent=self
            )

        if hasattr(self.file_translator, 'translation_worker'):
            self.file_translator.translation_worker.abort()

    def on_package_download_finished(self, status):
        if status == "start":
            self.download_progressbar.start()
            InfoBar.info(
                title=QCoreApplication.translate("MainWindow", "Information"),
                content=QCoreApplication.translate("MainWindow", "Downloading {} package").format(cfg.get(cfg.package).value),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.update_argos_remove_button_state(False)
        elif status == "success":
            self.download_progressbar.stop()
            InfoBar.success(
                title=QCoreApplication.translate("MainWindow", "Success"),
                content=QCoreApplication.translate("MainWindow", "Package installed successfully!"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.update_argos_remove_button_state(True)
            self.check_packages()
        elif status.startswith("error"):
            InfoBar.error(
                title=QCoreApplication.translate("MainWindow", "Error"),
                content=status,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=4000,
                parent=self
            )
            self.update_argos_remove_button_state(False)


if __name__ == "__main__":
    if cfg.get(cfg.dpiScale) != "Auto":
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))

    if os.name == 'nt':
        import ctypes
        myappid = u'icosane.celosia.filetranslate.100'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    locale = cfg.get(cfg.language).value
    fluentTranslator = FluentTranslator(locale)
    appTranslator = QTranslator()
    lang_path = os.path.join(res_dir, "resource", "lang")
    appTranslator.load(locale, "lang", ".", lang_path)

    app.installTranslator(fluentTranslator)
    app.installTranslator(appTranslator)

    window = MainWindow()
    window.show()
    #sys.excepthook = ErrorHandler()
    #sys.stderr = ErrorHandler()
    sys.exit(app.exec())
