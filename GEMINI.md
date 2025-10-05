# Session Management Logic (`start_new_session`)

This document describes the explicit session management mechanism for the AI translator, controlled by the `start_new_session` flag.

## How It Works

A boolean flag, `self.start_new_session`, located in the `TranslationHandler` class, is used to manage the lifecycle of an AI "conversation."

-   **`start_new_session = True`**: Signals that the next request to the AI must begin a completely new session, ignoring any previous history.
-   **`start_new_session = False`**: Signals that the next request is a continuation of the current session.

### When the Flag is Set to `True`

1.  **Application Initialization**: Set to `True` on startup in `TranslationHandler.__init__`.
2.  **Manual Session Reset**: When "AI Reset Translation Session" is triggered from the "Tools" menu (`TranslationHandler.reset_translation_session`).
3.  **AI Provider Change**: Changing the provider in settings also calls `reset_translation_session`.
4.  **Full Block Translation**: Before initiating a translation for an entire block (`TranslationHandler.translate_current_block`), as this is considered a large, distinct task.

### When the Flag is Set to `False`

The flag is automatically flipped to `False` after the first successful request within a new session. This occurs inside `TranslationHandler._prepare_session_for_request`, effectively "locking" the session for subsequent requests.

## Implementation Details

### Key Files

1.  `handlers/translation/translation_handler.py`
2.  `core/translation/session_manager.py`

### Modified Functions

-   **`handlers/translation/translation_handler.py`**:
    -   `__init__`: Initializes `self.start_new_session = True`.
    -   `reset_translation_session`: Sets `self.start_new_session = True`.
    -   `translate_current_block`: Sets `self.start_new_session = True`.
    -   `_prepare_session_for_request`: Reads the flag's state, passes it to `ensure_session`, and sets it to `False` after a session is successfully created/retrieved.

-   **`core/translation/session_manager.py`**:
    -   `ensure_session`: Now accepts `start_new_session: bool`. It creates a new session if `start_new_session` is `True` or if the `provider_key` has changed, ignoring the comparison of system prompts for session identification.

## Example Workflow

1.  **Launch:** `start_new_session` = `True`.
2.  **First Translation:** `_prepare_session_for_request` sees `True`, calls `ensure_session` with the `True` flag. A new session is created. `start_new_session` becomes `False`.
3.  **Glossary Change & "AI All":** `_attach_session_to_task` is called. `start_new_session` is now `False`. `_prepare_session_for_request` calls `ensure_session` with `False`. The manager sees no need to reset and simply updates the current system prompt for the existing session.
4.  **Manual Reset:** `reset_translation_session` is called. `start_new_session` becomes `True`. The next request will again start a new session.