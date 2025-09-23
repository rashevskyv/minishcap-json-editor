# --- START OF FILE handlers/translation/ai_worker.py ---
from PyQt5.QtCore import QObject, pyqtSignal
from typing import List, Dict, Optional, Any
from core.translation.providers import BaseTranslationProvider, ProviderResponse, TranslationProviderError
from .ai_prompt_composer import AIPromptComposer
from utils.logging_utils import log_debug

class AIWorker(QObject):
    success = pyqtSignal(ProviderResponse, dict)
    error = pyqtSignal(str, dict)
    finished = pyqtSignal()
    step_updated = pyqtSignal(int, str, int)

    def __init__(self, provider: BaseTranslationProvider, prompt_composer: AIPromptComposer, task_details: Dict[str, Any]):
        super().__init__()
        self.provider = provider
        self.prompt_composer = prompt_composer
        self.task_details = task_details

    def run(self):
        from components.ai_status_dialog import AIStatusDialog
        log_debug(f"AIWorker: Thread started for task type '{self.task_details.get('type')}'.")
        
        try:
            task_type = self.task_details.get('type')
            messages: List[Dict[str, str]] = []

            dialog_steps = self.task_details['dialog_steps']
            self.step_updated.emit(0, dialog_steps[0], AIStatusDialog.STATUS_IN_PROGRESS)
            
            if task_type == 'translate_preview':
                system, user, p_map = self.prompt_composer.compose_batch_request(**self.task_details['composer_args'])
                self.task_details['placeholder_map'] = p_map
                messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            elif task_type in ['translate_single', 'generate_variation']:
                system, user, p_map = self.prompt_composer.compose_variation_request(**self.task_details['composer_args'])
                self.task_details['placeholder_map'] = p_map
                messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            elif task_type == 'fill_glossary':
                system, user = self.prompt_composer.compose_glossary_request(**self.task_details['composer_args'])
                messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            else:
                raise ValueError(f"Unknown AI task type: {task_type}")

            step_text = f"Sending to AI... (Attempt {self.task_details.get('attempt', 1)}/{self.task_details.get('max_retries', 1)})"
            self.step_updated.emit(1, step_text, AIStatusDialog.STATUS_IN_PROGRESS)
            
            self.step_updated.emit(2, dialog_steps[2], AIStatusDialog.STATUS_IN_PROGRESS)
            
            provider_settings_override = self.task_details.get('provider_settings_override', {})
            response = self.provider.translate(messages, session=None, settings_override=provider_settings_override)
            
            self.success.emit(response, self.task_details)

        except (TranslationProviderError, ValueError, Exception) as e:
            log_debug(f"AIWorker: Exception caught in worker thread: {e}")
            self.error.emit(str(e), self.task_details)
        finally:
            log_debug("AIWorker: Task finished, emitting 'finished' signal.")
            self.finished.emit()