# --- START OF FILE handlers/ai_chat_handler.py ---
from typing import Dict, Optional
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QTextCursor
from .base_handler import BaseHandler
from components.ai_chat_dialog import AIChatDialog
from core.translation.session_manager import TranslationSessionManager
from core.translation.providers import ProviderResponse
from handlers.translation.ai_worker import AIWorker
from utils.logging_utils import log_debug, log_warning
from html import escape
import re
import markdown

class AIChatHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self.dialog: Optional[AIChatDialog] = None
        self.sessions: Dict[int, TranslationSessionManager] = {}
        self._worker: Optional[AIWorker] = None
        self._thread: Optional[QThread] = None
        self.system_prompt = "You are a helpful linguistic assistant specializing in video game localization."
        self._stream_buffer: Dict[int, str] = {}

    def _get_available_providers(self) -> dict:
        providers_data = {}
        config = getattr(self.mw, 'translation_config', {}).get('providers', {})
        for key, info in config.items():
            if key != 'disabled':
                display_name = key.replace('_', ' ').title()
                providers_data[key] = {
                    'display_name': display_name,
                    'model': info.get('model', 'default')
                }
        return providers_data

    def show_chat_window(self, initial_text: str = ""):
        if self.dialog is None:
            self.dialog = AIChatDialog(self.mw)
            self.dialog.message_sent.connect(self._handle_send_message)
            self.dialog.tabs.tabCloseRequested.connect(self._handle_tab_closed)
            self.dialog.add_tab_button.clicked.connect(self._add_new_chat_session)
            
            self._add_new_chat_session()

        if initial_text:
            current_tab = self.dialog.tabs.currentWidget()
            if current_tab:
                current_content = current_tab.input_edit.toPlainText()
                separator = "\n\n" if current_content.strip() else ""
                context_block = f"--- Context ---\n{initial_text.strip()}\n---"
                current_tab.input_edit.setPlainText(current_content + separator + context_block)
                current_tab.input_edit.moveCursor(QTextCursor.End)
        
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        
        current_tab = self.dialog.tabs.currentWidget()
        if current_tab:
            current_tab.input_edit.setFocus()

    def _add_new_chat_session(self):
        if not self.dialog: return

        new_tab = self.dialog.add_new_tab()
        providers = self._get_available_providers()
        new_tab.populate_models(providers)
        
        tab_index = self.dialog.tabs.indexOf(new_tab)
        self.sessions[tab_index] = TranslationSessionManager()

    def _handle_tab_closed(self, index: int):
        if index in self.sessions:
            del self.sessions[index]
            log_debug(f"AI Chat: Session for tab {index} has been removed.")
        else:
            if index in self.sessions:
                del self.sessions[index]
                log_debug(f"AI Chat: Session for tab index {index} has been removed.")

    def _handle_send_message(self, tab_index, message, provider_key):
        if self.dialog:
            html = f"""
            <table class='message-table'>
              <tr class='user-message-row'>
                <td class='prefix-cell'><b class='chat-prefix-user'>User:</b></td>
                <td class='content-cell'>{escape(message)}</td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)
            self.dialog.set_thinking_state(tab_index, True)

        provider = self.mw.translation_handler._prepare_provider(provider_key)
        if not provider:
            error_html = f"""
            <table class='message-table'>
              <tr class='ai-message-row'>
                <td class='prefix-cell'><b class='chat-prefix-ai' style='color:red;'>Error:</b></td>
                <td class='content-cell' style='color:red;'>Could not create AI provider '{provider_key}'.</td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, error_html)
            self.dialog.set_thinking_state(tab_index, False)
            return

        session_manager = self.sessions.get(tab_index)
        if not session_manager:
            session_manager = TranslationSessionManager()
            self.sessions[tab_index] = session_manager
            log_debug(f"AI Chat: Re-created missing session for tab index {tab_index}.")

        use_stream = True
        if provider_key == 'gemini' and provider.settings.get('base_url'):
            use_stream = False
            log_debug("AI Chat: Gemini with base_url detected, disabling streaming.")

        state = session_manager.ensure_session(
            provider_key=provider_key,
            base_system_prompt=self.system_prompt,
            full_system_prompt=self.system_prompt,
            supports_sessions=provider.supports_sessions,
            start_new_session=False
        )

        messages, session_payload = state.prepare_request({"role": "user", "content": message})
        
        task_details = {
            'type': 'chat_message_stream' if use_stream else 'chat_message',
            'tab_index': tab_index,
            'session_state': state,
            'session_user_message': message,
        }

        if self._thread and self._thread.isRunning():
            log_warning("AI Chat: An AI task is already running. Please wait.")
            self.dialog.set_thinking_state(tab_index, False)
            return

        self._thread = QThread()
        self._worker = AIWorker(provider, None, task_details)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        if use_stream:
            self._stream_buffer[tab_index] = ""
            self._worker.chunk_received.connect(self._on_ai_chunk_received)
            self._worker.success.connect(self._on_ai_stream_finished)
            self.dialog.start_ai_message(tab_index)
        else:
            self._worker.success.connect(self._on_ai_chat_success)
        
        self._worker.error.connect(self._on_ai_error)
        self._worker.finished.connect(self._cleanup_worker)

        self._thread.start()

    def _format_ai_response_for_display(self, text: str) -> str:
        text_no_leading_whitespace = text.lstrip()
        
        def wrap_tags(match):
            return f"<code>{match.group(0)}</code>"
        
        text_with_code_tags = re.sub(r'(\[[^\]]*\]|\{[^}]*\})', wrap_tags, escape(text_no_leading_whitespace))
        
        html_output = markdown.markdown(text_with_code_tags, extensions=['nl2br', 'fenced_code'])
        
        return html_output

    def _on_ai_chunk_received(self, context: dict, chunk: str):
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.append_stream_chunk(tab_index, escape(chunk))
            self._stream_buffer[tab_index] = self._stream_buffer.get(tab_index, "") + chunk
    
    def _on_ai_stream_finished(self, response: ProviderResponse, context: dict):
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            full_response = self._stream_buffer.get(tab_index, "")
            formatted_html = self._format_ai_response_for_display(full_response)
            
            self.dialog.set_thinking_state(tab_index, False)
            
            cursor = self.dialog.tabs.widget(tab_index).history_view.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            
            html = f"""
            <table class='message-table'>
              <tr class='ai-message-row'>
                <td class='prefix-cell'><b class='chat-prefix-ai'>AI:</b></td>
                <td class='content-cell'>{formatted_html}</td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)

            self._stream_buffer[tab_index] = ""
            
            state = context.get('session_state')
            user_content = context.get('session_user_message')
            if state and user_content:
                state.record_exchange(
                    user_content=user_content, 
                    assistant_content=response.text or full_response, 
                    conversation_id=response.conversation_id
                )

    def _on_ai_chat_success(self, response: ProviderResponse, context: dict):
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_thinking_state(tab_index, False)
            ai_response_text = response.text or "[No response]"
            
            formatted_html = self._format_ai_response_for_display(ai_response_text)
            html = f"""
            <table class='message-table'>
              <tr class='ai-message-row'>
                <td class='prefix-cell'><b class='chat-prefix-ai'>AI:</b></td>
                <td class='content-cell'>{formatted_html}</td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)
            
            state = context.get('session_state')
            user_content = context.get('session_user_message')
            if state and user_content:
                state.record_exchange(user_content=user_content, assistant_content=ai_response_text, conversation_id=response.conversation_id)

    def _on_ai_error(self, message: str, context: dict):
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_thinking_state(tab_index, False)
            html = f"""
            <table class='message-table'>
              <tr class='ai-message-row'>
                <td class='prefix-cell'><b class='chat-prefix-ai' style='color:red;'>Error:</b></td>
                <td class='content-cell' style='color:red;'>{escape(message)}</td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)

    def _cleanup_worker(self):
        tab_index = self._worker.task_details.get('tab_index') if self._worker else None
        if self.dialog and tab_index is not None:
            self.dialog.set_thinking_state(tab_index, False)
            
        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(1000)
            self._thread.deleteLater()
            self._thread = None
        if self._worker:
            self._worker.deleteLater()
            self._worker = None