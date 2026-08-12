"""Setup Wizard modal for first-run configuration."""
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Input, Label, Select, Static, TextArea, Checkbox
from textual.screen import ModalScreen
from textual.message import Message
from textual import events
from mycode.core.workspace import (
    ProviderManager, ProviderProfile, DEFAULT_PROVIDERS,
    provider_manager, workspace_manager
)
import json
import requests


class SetupWizardScreen(ModalScreen):
    """Multi-step setup wizard for first-run configuration."""

    STEPS = ["api_key", "provider", "model", "payload", "complete"]

    def __init__(self):
        super().__init__()
        self.current_step = 0
        self.api_key = ""
        self.selected_provider = None
        self.selected_model = ""
        self.raw_payload = {}
        self.available_models = []

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🚀 MyCode Setup Wizard", id="wizard-title"),
            Static("", id="wizard-step-indicator"),
            Container(id="wizard-content", classes="wizard-content"),
            Horizontal(
                Button("← Back", id="btn-back", variant="default", disabled=True),
                Button("Next →", id="btn-next", variant="primary"),
                Button("Launch MyCode", id="btn-launch", variant="success", disabled=True),
                id="wizard-buttons"
            ),
            id="wizard-container"
        )

    def on_mount(self) -> None:
        self.update_step()

    def update_step(self):
        step = self.STEPS[self.current_step]
        self.query_one("#wizard-step-indicator", Static).update(
            f"Step {self.current_step + 1} of {len(self.STEPS)}: {step.replace('_', ' ').title()}"
        )

        content = self.query_one("#wizard-content")
        content.remove_children()

        if step == "api_key":
            self._render_api_key_step(content)
        elif step == "provider":
            self._render_provider_step(content)
        elif step == "model":
            self._render_model_step(content)
        elif step == "payload":
            self._render_payload_step(content)
        elif step == "complete":
            self._render_complete_step(content)

        # Update button states
        back_btn = self.query_one("#btn-back", Button)
        next_btn = self.query_one("#btn-next", Button)
        launch_btn = self.query_one("#btn-launch", Button)

        back_btn.disabled = (self.current_step == 0)
        next_btn.disabled = (self.current_step == len(self.STEPS) - 1)
        launch_btn.disabled = (self.current_step != len(self.STEPS) - 1)

    def _render_api_key_step(self, content):
        content.mount(Label("Enter your API Key:", classes="wizard-label"))
        content.mount(Input(
            placeholder="Paste your API key here...",
            password=True,
            id="api-key-input"
        ))
        content.mount(Static(
            "Your API key will be saved securely to ~/.mycode/.env with 0600 permissions.",
            classes="wizard-hint"
        ))

    def _render_provider_step(self, content):
        content.mount(Label("Select LLM Provider:", classes="wizard-label"))

        options = []
        for i, p in enumerate(DEFAULT_PROVIDERS):
            options.append((f"{p['name']} ({p['base_url']})", str(i)))
        options.append(("Custom URL...", "custom"))

        content.mount(Select(options, id="provider-select", prompt="Choose a provider"))
        content.mount(Input(
            placeholder="https://custom.api.example.com/v1",
            id="custom-url-input"
        ))
        self.query_one("#custom-url-input", Input).display = False

    def _render_model_step(self, content):
        content.mount(Label("Select Model:", classes="wizard-label"))

        if self.available_models:
            options = [(m, m) for m in self.available_models]
            options.append(("Custom model ID...", "custom"))
            content.mount(Select(options, id="model-select", prompt="Choose a model"))
        else:
            content.mount(Static("Fetching models...", classes="wizard-loading"))
            self.run_worker(self._fetch_models(), thread=True)

        content.mount(Input(
            placeholder="Enter custom model ID",
            id="custom-model-input"
        ))
        self.query_one("#custom-model-input", Input).display = False

    def _fetch_models(self):
        """Fetch models from provider's /models endpoint."""
        if not self.selected_provider:
            return

        try:
            base_url = self.selected_provider["base_url"].rstrip("/")
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.available_models = [m["id"] for m in data.get("data", [])]
            else:
                # Fallback to known models
                self.available_models = self._get_fallback_models()
        except Exception:
            self.available_models = self._get_fallback_models()

        self.call_from_thread(self.update_step)

    def _get_fallback_models(self):
        """Get fallback models for known providers."""
        fallbacks = {
            "NVIDIA Nemotron": ["nvidia/nemotron-3-ultra", "nvidia/nemotron-4-340b", "nvidia/nemotron-3-8b"],
            "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "Ollama (Local)": ["llama3.1", "llama3.1:70b", "codellama", "mistral"],
            "Together AI": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"],
            "OpenRouter": ["anthropic/claude-3.5-sonnet", "anthropic/claude-3-opus", "google/gemini-pro"],
        }
        return fallbacks.get(self.selected_provider["name"], [])

    def _render_payload_step(self, content):
        content.mount(Label("Raw Payload (JSON) - Editable:", classes="wizard-label"))

        # Get default payload for selected provider
        default_payload = self._get_default_payload()
        default_payload["model"] = self.selected_model

        payload_text = json.dumps(default_payload, indent=2)

        content.mount(TextArea(
            payload_text,
            id="payload-editor",
            language="json",
            show_line_numbers=True,
            soft_wrap=False
        ))
        content.mount(Horizontal(
            Button("Validate JSON", id="btn-validate", variant="default"),
            Button("Reset to Defaults", id="btn-reset", variant="default"),
            id="payload-actions"
        ))

    def _get_default_payload(self):
        for p in DEFAULT_PROVIDERS:
            if p["name"] == self.selected_provider["name"]:
                return p["default_payload"].copy()
        return {
            "model": self.selected_model,
            "temperature": 0.2,
            "max_tokens": 4096,
            "top_p": 0.95,
        }

    def _render_complete_step(self, content):
        content.mount(Static("✅ Setup Complete!", classes="wizard-success"))
        content.mount(Static(
            "MyCode is ready to launch. Your configuration has been saved.\n"
            "You can reconfigure anytime via Command Palette (Ctrl+Shift+P) → 'Configure Provider'.",
            classes="wizard-hint"
        ))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            if self.current_step > 0:
                self.current_step -= 1
                self.update_step()
        elif event.button.id == "btn-next":
            if self._validate_current_step():
                self.current_step += 1
                self.update_step()
        elif event.button.id == "btn-launch":
            self._save_and_launch()
        elif event.button.id == "btn-validate":
            self._validate_payload()
        elif event.button.id == "btn-reset":
            self._reset_payload()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            if event.value == "custom":
                self.query_one("#custom-url-input", Input).display = True
                self.selected_provider = {"name": "Custom", "base_url": ""}
            else:
                self.query_one("#custom-url-input", Input).display = False
                idx = int(event.value)
                self.selected_provider = DEFAULT_PROVIDERS[idx]
        elif event.select.id == "model-select":
            if event.value == "custom":
                self.query_one("#custom-model-input", Input).display = True
                self.selected_model = ""
            else:
                self.query_one("#custom-model-input", Input).display = False
                self.selected_model = event.value

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "api-key-input":
            self.api_key = event.value
        elif event.input.id == "custom-url-input":
            if self.selected_provider and self.selected_provider.get("name") == "Custom":
                self.selected_provider["base_url"] = event.value
        elif event.input.id == "custom-model-input":
            self.selected_model = event.value

    def _validate_current_step(self) -> bool:
        step = self.STEPS[self.current_step]
        if step == "api_key":
            if not self.api_key.strip():
                self.notify("API key is required", severity="error")
                return False
        elif step == "provider":
            if not self.selected_provider:
                self.notify("Please select a provider", severity="error")
                return False
            if self.selected_provider.get("name") == "Custom" and not self.selected_provider.get("base_url"):
                self.notify("Custom provider URL is required", severity="error")
                return False
        elif step == "model":
            if not self.selected_model:
                self.notify("Please select a model", severity="error")
                return False
        elif step == "payload":
            # Validate JSON
            payload_text = self.query_one("#payload-editor", TextArea).text
            try:
                self.raw_payload = json.loads(payload_text)
            except json.JSONDecodeError as e:
                self.notify(f"Invalid JSON: {e}", severity="error")
                return False
        return True

    def _validate_payload(self):
        payload_text = self.query_one("#payload-editor", TextArea).text
        try:
            json.loads(payload_text)
            self.notify("✅ JSON is valid", severity="information")
        except json.JSONDecodeError as e:
            self.notify(f"❌ Invalid JSON: {e}", severity="error")

    def _reset_payload(self):
        default_payload = self._get_default_payload()
        default_payload["model"] = self.selected_model
        self.query_one("#payload-editor", TextArea).text = json.dumps(default_payload, indent=2)
        self.notify("Payload reset to defaults", severity="information")

    def _save_and_launch(self):
        """Save configuration and dismiss wizard."""
        # Get final payload
        payload_text = self.query_one("#payload-editor", TextArea).text
        try:
            self.raw_payload = json.loads(payload_text)
        except:
            pass

        # Create provider profile
        profile = ProviderProfile(
            name=self.selected_provider["name"],
            api_key=self.api_key,
            base_url=self.selected_provider["base_url"],
            model=self.selected_model,
            raw_payload=self.raw_payload,
            is_default=True
        )

        # Save to provider manager
        provider_manager.add_profile(profile)

        # Save API key to .env
        from mycode.core.config import save_api_key
        save_api_key(self.api_key)

        self.notify("Configuration saved! Launching MyCode...", severity="information")
        self.dismiss(True)


class ProviderSettingsScreen(ModalScreen):
    """Provider settings modal for re-configuring providers."""

    def __init__(self):
        super().__init__()
        self.current_step = 0
        # Pre-fill with active profile
        active = provider_manager.get_active()
        if active:
            self.api_key = active.api_key
            self.selected_provider = next(
                (p for p in DEFAULT_PROVIDERS if p["name"] == active.name),
                {"name": "Custom", "base_url": active.base_url}
            )
            self.selected_model = active.model
            self.raw_payload = active.raw_payload
            self.available_models = []
        else:
            self.api_key = ""
            self.selected_provider = None
            self.selected_model = ""
            self.raw_payload = {}
            self.available_models = []

    def compose(self) -> ComposeResult:
        yield Container(
            Static("⚙️ Provider Settings", id="wizard-title"),
            Static("", id="wizard-step-indicator"),
            Container(id="wizard-content", classes="wizard-content"),
            Horizontal(
                Button("← Back", id="btn-back", variant="default"),
                Button("Next →", id="btn-next", variant="primary"),
                Button("Save", id="btn-save", variant="success", disabled=True),
                id="wizard-buttons"
            ),
            id="wizard-container"
        )

    def on_mount(self) -> None:
        self.update_step()

    def update_step(self):
        self._render_current_step()

    def _render_current_step(self):
        content = self.query_one("#settings-content")
        content.remove_children()
        self._render_settings(content)

    def _save(self):
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
            is_default=True,
        )
        provider_manager.add_profile(profile)
        self.notify("Provider settings saved!", severity="information")
        self.dismiss(True)


class PayloadEditorScreen(ModalScreen):
    """Raw payload JSON editor with syntax highlighting."""

    def __init__(self, payload: dict, on_save_callback=None):
        super().__init__()
        self.payload = payload
        self.on_save_callback = on_save_callback

    def compose(self) -> ComposeResult:
        yield Container(
            Static("📝 Raw Payload Editor", id="editor-title"),
            TextArea(
                json.dumps(self.payload, indent=2),
                id="payload-editor",
                language="json",
                show_line_numbers=True,
                soft_wrap=False
            ),
            Horizontal(
                Button("Validate", id="btn-validate", variant="default"),
                Button("Reset", id="btn-reset", variant="default"),
                Button("Cancel", id="btn-cancel", variant="error"),
                Button("Save", id="btn-save", variant="success"),
                id="editor-buttons"
            ),
            id="editor-container"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-validate":
            self._validate()
        elif event.button.id == "btn-reset":
            self.query_one("#payload-editor", TextArea).text = json.dumps(self.payload, indent=2)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()

    def _validate(self):
        text = self.query_one("#payload-editor", TextArea).text
        try:
            json.loads(text)
            self.notify("✅ Valid JSON", severity="information")
        except json.JSONDecodeError as e:
            self.notify(f"❌ Invalid JSON: {e}", severity="error")

    def _save(self):
        text = self.query_one("#payload-editor", TextArea).text
        try:
            payload = json.loads(text)
            if self.on_save_callback:
                self.on_save_callback(payload)
            self.dismiss(payload)
        except json.JSONDecodeError as e:
            self.notify(f"❌ Invalid JSON: {e}", severity="error")