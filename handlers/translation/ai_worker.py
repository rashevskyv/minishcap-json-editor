# handlers/translation/ai_worker.py ---
from PyQt5.QtCore import QObject, pyqtSignal
from typing import List, Dict, Optional, Any
import json
from core.translation.providers import BaseTranslationProvider, ProviderResponse, TranslationProviderError
from .ai_prompt_composer import AIPromptComposer
from utils.logging_utils import log_debug

class AIWorker(QObject):
    success = pyqtSignal(ProviderResponse, dict)
    error = pyqtSignal(str, dict)
    finished = pyqtSignal()
    step_updated = pyqtSignal(int, str, int)
    
    chunk_translated = pyqtSignal(int, str, dict)
    total_chunks_calculated = pyqtSignal(int, int)
    translation_cancelled = pyqtSignal()
    progress_updated = pyqtSignal(int)

    def __init__(self, provider: BaseTranslationProvider, prompt_composer: AIPromptComposer, task_details: Dict[str, Any]):
        super().__init__()
        self.provider = provider
        self.prompt_composer = prompt_composer
        self.task_details = task_details
        self.is_cancelled = False

    def cancel(self):
        log_debug("AIWorker: Cancellation requested.")
        self.is_cancelled = True

    def _clean_json_response(self, text: str) -> str:
        stripped_text = (text or '').strip()
        if stripped_text.startswith("```") and stripped_text.endswith("```"):
            lines = stripped_text.splitlines()
            if len(lines) > 1:
                content_lines = lines[1:-1]
                joined_content = "\n".join(content_lines).strip()
                if joined_content.startswith("json"):
                    joined_content = joined_content[4:].strip()
                return joined_content
            else:
                return ""
        return stripped_text

    def run(self):
        from components.ai_status_dialog import AIStatusDialog
        log_debug(f"AIWorker: Thread started for task type '{self.task_details.get('type')}'.")
        
        try:
            task_type = self.task_details.get('type')
            messages: List[Dict[str, str]] = []

            if task_type == 'build_glossary':
                system_prompt = self.task_details.get('system_prompt', '')
                user_template = self.task_details.get('user_prompt_template', '{text_chunk}')
                chunks: List[str] = self.task_details.get('chunks', [])
                dialog_steps = self.task_details.get('dialog_steps', [])
                total_chunks = len(chunks)
                aggregated_terms: List[Dict[str, Any]] = []

                self.total_chunks_calculated.emit(total_chunks, 0)
                if dialog_steps:
                    self.step_updated.emit(0, dialog_steps[0], AIStatusDialog.STATUS_IN_PROGRESS)

                for idx, chunk in enumerate(chunks):
                    if self.is_cancelled:
                        log_debug("AIWorker: Glossary build cancelled before processing chunk.")
                        self.translation_cancelled.emit()
                        return

                    self.progress_updated.emit(idx + 1)
                    step_text = f"Processing chunk {idx + 1}/{total_chunks}"
                    self.step_updated.emit(1, step_text, AIStatusDialog.STATUS_IN_PROGRESS)

                    user_prompt = user_template.format(text_chunk=chunk)
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]

                    try:
                        response = self.provider.translate(messages, session=None)
                        cleaned_text = self._clean_json_response(response.text)
                        parsed = json.loads(cleaned_text) if cleaned_text else []
                        if isinstance(parsed, list):
                            aggregated_terms.extend(parsed)
                        else:
                            log_debug(f"AIWorker: Glossary chunk {idx + 1} returned non-list response: {parsed}")
                    except (TranslationProviderError, json.JSONDecodeError) as exc:
                        log_debug(f"AIWorker: Error while building glossary chunk {idx + 1}: {exc}")
                        if not self.is_cancelled:
                            self.error.emit(str(exc), self.task_details)
                        return

                    if self.is_cancelled:
                        log_debug("AIWorker: Glossary build cancelled after chunk response.")
                        self.translation_cancelled.emit()
                        return

                aggregated_payload = ProviderResponse(
                    text=json.dumps(aggregated_terms, ensure_ascii=False),
                    raw_payload=aggregated_terms
                )
                if dialog_steps:
                    self.step_updated.emit(1, dialog_steps[1], AIStatusDialog.STATUS_DONE)
                    self.step_updated.emit(2, dialog_steps[2], AIStatusDialog.STATUS_DONE)
                    self.step_updated.emit(3, dialog_steps[3], AIStatusDialog.STATUS_DONE)
                self.success.emit(aggregated_payload, self.task_details)
                return

            if task_type == 'translate_block_chunked':
                CHUNK_SIZE = 10
                source_items = self.task_details['source_items']
                chunks = [source_items[i:i + CHUNK_SIZE] for i in range(0, len(source_items), CHUNK_SIZE)]
                chunks_to_skip = self.task_details.get('chunks_to_skip', set())
                self.total_chunks_calculated.emit(len(chunks), len(chunks_to_skip))
                
                for i, chunk in enumerate(chunks):
                    if i in chunks_to_skip:
                        log_debug(f"AIWorker: Skipping already translated chunk {i + 1}/{len(chunks)}.")
                        continue

                    if self.is_cancelled:
                        log_debug("AIWorker: Translation cancelled by user before processing chunk.")
                        self.translation_cancelled.emit()
                        return

                    max_retries = self.task_details.get('max_retries', 3)
                    current_retry = 0
                    
                    while current_retry < max_retries:
                        if self.is_cancelled:
                            log_debug("AIWorker: Translation cancelled during retry loop.")
                            break

                        composer_args_for_chunk = self.task_details['composer_args'].copy()
                        composer_args_for_chunk['source_items'] = chunk
                        system, user, p_map_for_chunk = self.prompt_composer.compose_batch_request(**composer_args_for_chunk)
                        
                        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
                        
                        self.progress_updated.emit(i + 1)
                        self.step_updated.emit(1, f"Translating chunk {i + 1}/{len(chunks)} (Attempt {current_retry + 1})", AIStatusDialog.STATUS_IN_PROGRESS)
                        
                        try:
                            response = self.provider.translate(messages, session=None)
                            
                            if self.is_cancelled:
                                log_debug("AIWorker: Translation cancelled during network request. Discarding response.")
                                break

                            cleaned_text = self._clean_json_response(response.text)
                            parsed_response = json.loads(cleaned_text)
                            translated_items = parsed_response.get("translated_strings", [])
                            
                            if len(translated_items) == len(chunk):
                                task_details_for_chunk = self.task_details.copy()
                                task_details_for_chunk['placeholder_map'] = p_map_for_chunk
                                self.chunk_translated.emit(i, cleaned_text, task_details_for_chunk)
                                break
                            else:
                                log_debug(f"AIWorker: Line count mismatch in chunk {i}. Expected {len(chunk)}, got {len(translated_items)}. Retrying...")
                                current_retry += 1

                        except (TranslationProviderError, json.JSONDecodeError) as e:
                            log_debug(f"AIWorker: Error translating chunk {i}: {e}. Retrying...")
                            current_retry += 1
                    
                    if self.is_cancelled:
                        self.translation_cancelled.emit()
                        return

                    if current_retry >= max_retries:
                        self.error.emit(f"Failed to translate chunk {i+1} after {current_retry} attempts.", self.task_details)
                        return
                
                return

            dialog_steps = self.task_details['dialog_steps']
            self.step_updated.emit(0, dialog_steps[0], AIStatusDialog.STATUS_IN_PROGRESS)
            
            precomposed = self.task_details.get('precomposed_prompt')
            session_info = self.task_details.get('session') if isinstance(self.task_details.get('session'), dict) else None
            session_payload = None

            if precomposed and not session_info:
                messages = precomposed
            elif task_type == 'translate_preview':
                system, user, p_map = self.prompt_composer.compose_batch_request(**self.task_details['composer_args'])
                if 'placeholder_map' not in self.task_details:
                    self.task_details['placeholder_map'] = p_map
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            elif task_type in ['translate_single', 'generate_variation', 'glossary_notes_variation']:
                system, user, p_map = self.prompt_composer.compose_variation_request(**self.task_details['composer_args'])
                if 'placeholder_map' not in self.task_details:
                    self.task_details['placeholder_map'] = p_map
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

            elif task_type == 'fill_glossary':
                system, user = self.prompt_composer.compose_glossary_request(**self.task_details['composer_args'])
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            elif task_type == 'glossary_occurrence_update':
                system, user, p_map = self.prompt_composer.compose_glossary_occurrence_update_request(**self.task_details['composer_args'])
                if 'placeholder_map' not in self.task_details:
                    self.task_details['placeholder_map'] = p_map
                if session_info and session_info.get('state'):
                    user_message = {'role': 'user', 'content': user}
                    session_info['user_message'] = user_message
                    self.task_details['session_user_message'] = user
                    messages, session_payload = session_info['state'].prepare_request(user_message)
                else:
                    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            else:
                messages = [{"role": "system", "content": self.task_details.get('composer_args', {}).get('system_prompt', '')}]

            step_text = f"Sending to AI... (Attempt {self.task_details.get('attempt', 1)}/{self.task_details.get('max_retries', 1)})"
            self.step_updated.emit(1, step_text, AIStatusDialog.STATUS_IN_PROGRESS)
            
            self.step_updated.emit(2, dialog_steps[2], AIStatusDialog.STATUS_IN_PROGRESS)
            
            provider_settings_override = self.task_details.get('provider_settings_override', {})
            response = self.provider.translate(messages, session=session_payload, settings_override=provider_settings_override)

            if self.is_cancelled:
                log_debug("AIWorker: Operation cancelled after network request. Discarding response.")
                self.translation_cancelled.emit()
                return
            
            self.success.emit(response, self.task_details)


        except (TranslationProviderError, ValueError, Exception) as e:
            log_debug(f"AIWorker: Exception caught in worker thread: {e}")
            if not self.is_cancelled:
                self.error.emit(str(e), self.task_details)
        finally:
            log_debug("AIWorker: Task finished, emitting 'finished' signal.")
            self.finished.emit()

