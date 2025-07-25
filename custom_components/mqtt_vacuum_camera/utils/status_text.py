"""
Version: 2025.6.0
Status text of the vacuum cleaners.
Clas to handle the status text of the vacuum cleaners.
"""

from __future__ import annotations

import asyncio
import json

from valetudo_map_parser.config.types import JsonType, PilPNG

from ..const import DOMAIN, LOGGER

LOGGER.propagate = True


class StatusText:
    """
    Status text of the vacuum cleaners.
    """

    def __init__(self, hass, camera_shared):
        self.hass = hass
        self._shared = camera_shared
        self.file_name = self._shared.file_name
        self._translations_path = hass.config.path(
            f"custom_components/{DOMAIN}/translations/"
        )

    async def async_load_translations(self, language: str) -> JsonType:
        """
        Load the user selected language json file and return it asynchronously.
        """
        file_name = f"{language}.json"
        file_path = f"{self._translations_path}/{file_name}"

        def _read_translation_file(path: str) -> JsonType:
            """Helper function to read translation file synchronously."""
            try:
                with open(path) as file:
                    return json.load(file)
            except FileNotFoundError:
                LOGGER.warning(
                    "%s Not found. Report to the author that %s is missing.",
                    path,
                    language,
                )
                return None
            except json.JSONDecodeError:
                LOGGER.warning("%s is not a valid JSON file.", path, exc_info=True)
                return None

        try:
            # Use asyncio.to_thread for non-blocking file operations
            return await asyncio.to_thread(_read_translation_file, file_path)
        except Exception as e:
            LOGGER.warning("Error loading translation file %s: %s", file_path, str(e))
            return None

    async def async_get_vacuum_status_translation(self, language: str) -> any:
        """
        Get the vacuum status translation asynchronously.
        @param language: String IT, PL, DE, ES, FR, EN.
        @return: Json data or None.
        """
        translations = await self.async_load_translations(language)

        # Check if the translations file is loaded.
        if translations is None:
            return None

        vacuum_status_options = (
            translations.get("selector", {}).get("vacuum_status", {}).get("options", {})
        )
        return vacuum_status_options

    async def async_translate_vacuum_status(self) -> str:
        """Return the translated status asynchronously."""
        status = self._shared.vacuum_state
        language = self._shared.user_language

        # Check if status is None and provide fallback
        if status is None:
            LOGGER.warning("Vacuum state is None, falling back to 'not available'")
            return "not available"

        if not language:
            return status.capitalize()
        translations = await self.async_get_vacuum_status_translation(language)
        if translations is not None and status in translations:
            return translations[status]
        return status.capitalize()

    async def async_get_status_text(self, text_img: PilPNG) -> tuple[list[str], int]:
        """
        Compose the image status text asynchronously.
        :param text_img: Image to draw the text on.
        :return status_text, text_size: List of the status text and the text size.
        """
        status_text = ["If you read me, something really went wrong.."]  # default text
        text_size_coverage = 1.5  # resize factor for the text
        text_size = self._shared.vacuum_status_size  # default text size
        charge_level = "\u03de"  # unicode Koppa symbol
        charging = "\u2211"  # unicode Charging symbol
        vacuum_state = await self.async_translate_vacuum_status()

        # Check if vacuum_state is None and provide fallback
        if vacuum_state is None:
            LOGGER.warning("Vacuum state is None, falling back to 'not available'")
            vacuum_state = "not available"

        if self._shared.show_vacuum_state:
            status_text = [f"{self.file_name}: {vacuum_state}"]
            if not self._shared.vacuum_connection:
                status_text = [f"{self.file_name}: Disconnected from MQTT?"]
            else:
                if self._shared.current_room:
                    try:
                        in_room = self._shared.current_room.get("in_room", None)
                    except (ValueError, KeyError):
                        LOGGER.debug("No in_room data.")
                    else:
                        if in_room:
                            status_text.append(f" ({in_room})")
                if self._shared.vacuum_state == "docked":
                    if int(self._shared.vacuum_battery) <= 99:
                        status_text.append(" \u00b7 ")
                        status_text.append(f"{charging}{charge_level} ")
                        status_text.append(f"{self._shared.vacuum_battery}%")
                        self._shared.vacuum_bat_charged = False
                    else:
                        status_text.append(" \u00b7 ")
                        status_text.append(f"{charge_level} ")
                        status_text.append("Ready.")
                        self._shared.vacuum_bat_charged = True
                else:
                    status_text.append(" \u00b7 ")
                    status_text.append(f"{charge_level}")
                    status_text.append(f" {self._shared.vacuum_battery}%")
                    # When vacuum is not docked, it's not fully charged (should stream)
                    self._shared.vacuum_bat_charged = False
                if text_size >= 50:
                    text_pixels = sum(len(text) for text in status_text)
                    text_size = int(
                        (text_size_coverage * text_img.width) // text_pixels
                    )

        # Final check to ensure status_text is never None
        if status_text is None:
            LOGGER.warning("Status text is None, falling back to 'not available'")
            status_text = [f"{self.file_name}: not available"]

        return status_text, text_size
