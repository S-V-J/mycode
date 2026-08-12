"""Provider Settings modal - re-accessible via Command Palette."""
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Input, Label, Select, Static, TextArea
from textual.screen import ModalScreen
from textual.message import Message
import json

from mycode.core.workspace import (
    provider_manager, DEFAULT_PROVIDERS, ProviderProfile
)


class ProviderSettingsScreen(ModalScreen):
    """Re-configurable provider settings."""

    def __init__(self):
        super().__init__()
        self.api_key = ""
        self.selected_provider = None
        self.selected_model = ""
        self.raw_payload = {}
        self.available_models = []
        self.editing_profile_id = None

    def compose(self) -> ComposeResult:
        yield Container(
            Static("⚙️ Provider Settings", id="settings-title"),
            Container(id="settings-content"),
            Horizontal(
                Button("← Cancel", id="btn-cancel", variant="error"),
                Button("💾 Save", id="btn-save", variant="success"),
                id="settings-buttons"
            ),
            id="settings-container"
        )

    def on_mount(self) -> None:
        content = self.query_one("#settings-content")
        active = provider_manager.get_active()

        if active:
            self.editing_profile_id = active.id
            self.api_key = active.api_key
            self.selected_model = active.model
            self.raw_payload = active.raw_payload.copy()
            self.selected_provider = next(
                (p for p in DEFAULT_PROVIDERS if p["name"] == active.name),
                {"name": active.name, "base_url": active.base_url}
            )
        else:
            self.selected_provider = DEFAULT_PROVIDERS[0]
            self.raw_payload = DEFAULT_PROVIDERS[0]["default_payload"].copy()

        self._render_settings(content)

    def _render_settings(self, content):
        content.remove_children()

        # API Key
        content.mount(Label("API Key:", classes="settings-label"))
        content.mount(Input(
            value=self.api_key,
            placeholder="Paste API key...",
            password=True,
            id="settings-api-key"
        ))

        # Provider Selection
        content.mount(Label("Provider:", classes="settings-label"))
        options = [(f"{p['name']} ({p['base_url']})", str(i))
                   for i, p in enumerate(DEFAULT_PROVIDERS)]
        options.append(("Custom URL...", "custom"))

        current_idx = "0"
        if self.selected_provider:
            for i, p in enumerate(DEFAULT_PROVIDERS):
                if p["name"] == self.selected_provider.get("name"):
                    current_idx = str(i)
                    break

        content.mount(Select(
            options, id="settings-provider", value=current_idx
        ))
        content.mount(Input(
            value=self.selected_provider.get("base_url", "") if self.selected_provider else "",
            placeholder="https://custom.api.example.com/v1",
            id="settings-custom-url"
        ))

        # Model Selection
        content.mount(Label("Model:", classes="settings-label"))
        if self.available_models:
            model_options = [(m, m) for m in self.available_models]
            model_options.append(("Custom...", "custom"))
            current_model = self.selected_model if self.selected_model in self.available_models else "custom"
            content.mount(Select(model_options, id="settings-model", value=current_model))
        else:
            content.mount(Select(
                [("Loading models...", "")], id="settings-model", disabled=True
            ))
            self.run_worker(self._fetch_models, thread=True)

        content.mount(Input(
            value=self.selected_model,
            placeholder="Custom model ID",
            id="settings-custom-model"
        ))

        # Raw Payload
        content.mount(Label("Raw Payload (JSON):", classes="settings-label"))
        payload_text = json.dumps(self.raw_payload, indent=2)
        content.mount(TextArea(
            payload_text,
            id="settings-payload",
            language="json",
            show_line_numbers=True,
            soft_wrap=False
        ))

    def _fetch_models(self):
        """Fetch models from provider."""
        if not self.selected_provider:
            return
        try:
            base_url = self.selected_provider["base_url"].rstrip("/")
            headers = {"Authorization": f"Bearer {self.api_key}"}
            import requests
            response = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                self.available_models = [m["id"] for m in response.json().get("data", [])]
            else:
                self.available_models = self._get_fallback_models()
        except Exception:
            self.available_models = self._get_fallback_models()
        self.call_from_thread(self._render_settings, self.query_one("#settings-content"))

    def _get_fallback_models(self):
        """Fallback models for known providers."""
        fallbacks = {
            "NVIDIA Nemotron": ["nvidia/nemotron-3-ultra", "nvidia/nemotron-4-340b"],
            "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "Ollama (Local)": ["llama3.1", "mistral"],
            "Together AI": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"],
            "OpenRouter": ["anthropic/claude-3.5-sonnet", "google/gemini-pro"],
        }
        return fallbacks.get(self.selected_provider.get("name", ""), [])

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "settings-provider":
            if event.value == "custom":
                self.query_one("#settings-custom-url").display = True
                self.selected_provider = {"name": "Custom", "base_url": ""}
            else:
                self.query_one("#settings-custom-url").display = False
                idx = int(event.value)
                self.selected_provider = DEFAULT_PROVIDERS[idx]
                self.available_models = []
                self.run_worker(self._fetch_models, thread=True)

        elif event.select.id == "settings-model":
            if event.value == "custom":
                self.query_one("#settings-custom-model").display = True
                self.selected_model = ""
            else:
                self.query_one("#settings-custom-model").display = False
                self.selected_model = event.value

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "settings-api-key":
            self.api_key = event.value
        elif event.input.id == "settings-custom-url":
            if self.selected_provider:
                self.selected_provider["base_url"] = event.value
        elif event.input.id == "settings-custom-model":
            self.selected_model = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(False)
        elif event.button.id == "btn-save":
            self._save()

    def _save(self):
        """Save provider settings."""
        try:
            payload_text = self.query_one("#settings-payload", TextArea).text
            self.raw_payload = json.loads(payload_text)
        except json.JSONDecodeError:
            self.notify("Invalid JSON in payload", severity="error")
            return

        if not self.selected_model:
            self.notify("Model is required", severity="error")
            return

        profile = ProviderProfile(
            name=self.selected_provider["name"],
            api_key=self.api_key,
            base_url=self.selected_provider.get("base_url", ""),
            model=self.selected_model,
            raw_payload=self.raw_payload,
            is_default=True
        )

        if self.editing_profile_id:
            # Update existing
            for i, p in enumerate(provider_manager.providers):
                if p.id == self.editing_profile_id:
                    provider_manager.providers[i] = profile
                    provider_manager.active_profile_id = profile.id
                    provider_manager.save()
                    break
        else:
            provider_manager.add_profile(profile)

        self.notify("Provider settings saved!", severity="information")
        self.post_message(self.ProfileSaved())
        self.dismiss(True)

    class ProfileSaved(Message):
        pass
