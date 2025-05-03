from enum import Enum
import os, sys
from pathlib import Path
from ctranslate2 import get_cuda_device_count
from PyQt6.QtCore import QLocale
from qfluentwidgets import (qconfig, QConfig, OptionsConfigItem, Theme,
                            OptionsValidator, EnumSerializer, ConfigSerializer)


class ArgosPathManager:
    """Manages Argos Translate directory configuration"""

    @staticmethod
    def initialize():
        """Set up custom directories for Argos Translate"""
        # Set base directory
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)  # PyInstaller bundle
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        ARGOS_PACKAGES_DIR = os.path.join(base_dir, "models", "argostranslate")
        os.makedirs(ARGOS_PACKAGES_DIR, exist_ok=True)

        # Set environment variables
        os.environ.update({
            "XDG_DATA_HOME": str(Path(ARGOS_PACKAGES_DIR) / "data"),
            "XDG_CONFIG_HOME": str(Path(ARGOS_PACKAGES_DIR) / "config"),
            "XDG_CACHE_HOME": str(Path(ARGOS_PACKAGES_DIR) / "cache"),
            "ARGOS_PACKAGES_DIR": str(Path(ARGOS_PACKAGES_DIR) / "data" / "argos-translate" / "packages"),
            "ARGOS_TRANSLATE_DATA_DIR": str(Path(ARGOS_PACKAGES_DIR) / "data"),
            "ARGOS_DEVICE_TYPE": "cuda" if get_cuda_device_count() != 0 else "cpu"
        })

        # Create directories
        Path(os.environ["ARGOS_PACKAGES_DIR"]).mkdir(parents=True, exist_ok=True)

        return ARGOS_PACKAGES_DIR


# Initialize Argos paths BEFORE any Argos Translate imports
ArgosPathManager.initialize()

from argostranslate import argospm

class Language(Enum):
    """ Language enumeration """

    ENGLISH = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    RUSSIAN = QLocale(QLocale.Language.Russian, QLocale.Country.Russia)
    AUTO = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)

class LanguageSerializer(ConfigSerializer):
    """ Language serializer """

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        return Language(QLocale(value)) if value != "Auto" else Language.AUTO

class Device(Enum):
    CPU = "cpu"
    CUDA = "cuda"

class DeviceSerializer(ConfigSerializer):
    """ Device serializer """

    def __init__(self):
        self.device_map = {device.value: device for device in Device}

    def serialize(self, device):
        return device.value

    def deserialize(self, value: str):
        device = self.device_map.get(value)
        if device is None:
            raise ValueError(f"Invalid device: {value}")
        return device


available_packages = argospm.get_available_packages()

TranslationPackage = Enum(
    'TranslationPackage',
    {
        **{"NONE": "None"},
        **{f"{pkg.from_code.upper()}_TO_{pkg.to_code.upper()}": f"{pkg.from_code}_{pkg.to_code}"
           for pkg in available_packages}
    }
)

class TranslationPackageSerializer(ConfigSerializer):
    """ Translation package serializer """

    def __init__(self):
        self.package_map = {package.value: package for package in TranslationPackage}

    def serialize(self, package):
        return package.value if package != TranslationPackage.NONE else "None"

    def deserialize(self, value: str):
        if value == "None":
            return TranslationPackage.NONE
        package = self.package_map.get(value)
        if package is None:
            raise ValueError(f"Invalid translation package: {value}")
        return package

class Config(QConfig):
    language = OptionsConfigItem(
        "Settings", "language", QLocale.Language.English, OptionsValidator(Language), LanguageSerializer(), restart=True)
    themeMode = OptionsConfigItem("Window", "themeMode", Theme.AUTO,
                                OptionsValidator(Theme), EnumSerializer(Theme), restart=True)
    device = OptionsConfigItem(
        "whisper", "device", Device.CPU, OptionsValidator(Device), DeviceSerializer(), restart=False)
    dpiScale = OptionsConfigItem(
        "Settings", "DpiScale", "Auto", OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]), restart=True)
    package = OptionsConfigItem(
        "Translation", "package", TranslationPackage.NONE, OptionsValidator(TranslationPackage), TranslationPackageSerializer(), restart=False)


cfg = Config()
qconfig.load('config/config.json', cfg)
