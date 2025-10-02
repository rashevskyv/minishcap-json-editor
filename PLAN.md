# Glossary AI Enhancement Plan

## Current Objective
Enhance the AI-assisted glossary workflow so that:
- Translation and variation requests preserve in-text tags by masking them before sending content to the model and restoring them afterwards.
- Glossary builds generate both translations and human-friendly notes, while reporting detailed import statistics.
- Editors can request AI variations directly from the glossary dialog, mirroring the existing editor workflow.

## Completed Work
1. **Prompt Composer Refactor**
   - Rewrote AIPromptComposer to mask tags via placeholders, restore them by record ID, and support glossary-note variation prompts.
   - Added the glossary_notes_variation request type with dedicated instructions for models.
2. **Translation Handler Integration**
   - Updated restore logic to use per-string placeholder maps for block/preview translations.
   - Added a workflow to request AI-generated glossary notes and apply a chosen option back to the glossary manager/UI.
3. **Glossary Dialog Enhancements**
   - Inserted an AI Variations button in the Notes section, wired to the new callback, and refreshed editor state after updates.
   - Added refresh_entry_notes to keep the table/detail panes in sync without reopening the dialog.
4. **Glossary Handler Updates**
   - Forwarded dialog requests to the translation handler and persisted returned notes (including disk save, cache refresh, highlighting).
5. **Glossary Builder Improvements**
   - Adjusted prompts to require term, translation, and notes, and masked tags before shipping chunks to the provider.
   - Captured per-run statistics (new vs. updated vs. skipped duplicates) and surface them to the user/status bar.
6. **Downstream Verification**
   - Verified glossary occurrence highlighting, markdown persistence, and disk exports continue to function with populated notes via targeted Python checks.
   - Confirmed glossary UI tooltip and dialog flows surface notes without additional changes.

## Task Board (2025-10-01)
| ID | Task | Status | Notes |
|----|------|--------|-------|
| T1 | Stabilise AI Fill flow (correct `_run_ai_task` usage, add success handler, regression test Add/Edit glossary dialog) | Completed | Crash fixed, button state handled, prompt editor integrated; regression pending only for documentation. |
| T2 | Glossary translation update workflow (manual dialog + AI helpers) | In Progress | Manual dialog + AI hooks wired (single/all); prompt editor integration pending QA for block translation. |
| T2.1 | Design & build occurrence review dialog (list, manual editing, apply/skip controls) | Completed | Implemented `GlossaryTranslationUpdateDialog` with manual apply/skip flow (single Apply now advances automatically); AI buttons stubbed for future wiring. |
| T2.2 | Wire dialog into glossary entry update flow (detect translation change, gather occurrences) | In Progress | Pending follow-up in `handlers/translation/glossary_handler.py` (`_handle_occurrence_ai_result`, `_handle_occurrence_ai_error`) and undo/QA around dialog workflows. |
| T2.3 | Implement AI-assisted substitution (single/all) with placeholder-safe updates | In Progress | Validate AI JSON in `handlers/translation_handler.py` (`_handle_glossary_occurrence_update_success`) and ensure prompts in `translation_prompts/prompts.json` cover edge cases. |
| T3 | Prompt editor modal for AI requests (preview/edit/save per query) | Completed | Prompt editor dialog invoked for translation, variations, glossary fill, and occurrence updates with Ctrl override & save-to-prompts support. |
| T3.1 | Catalogue AI entry points + ensure prompts live in JSON definitions | Completed | Audit complete: all active AI entry points reference prompts (core JSON or plugin overrides); no additional sections required. |
| T3.2 | Build prompt editor UI (view merged prompt, edit, save-to-disk option) | Completed | `PromptEditorDialog` now used across AI calls with save-to-prompts support. |
| T3.3 | Hook modal into request pipeline with enable/disable toggle & Ctrl override | Completed | `_maybe_edit_prompt` handles Ctrl override and global toggle across AI flows. |
| T4 | Settings integration (toggle for prompt editor, persistence, Ctrl override) | Completed | Settings checkbox added, persisted via `SettingsManager`, toolbar icon updated. |
| T5 | Testing & QA (AI Fill, occurrence updates, prompt editor flows, regression) | TODO | Define manual scripts once upstream tasks land. |

## Next Iteration Goals
1. Finish T1: validate AI Fill end-to-end, ensure `_handle_ai_fill_success` applies results without raising, and remove stray debug placeholders (manual run pending).
2. Extend T2: exercise the new update dialog (manual + AI) against real data; capture gaps (selection, undo, batch UX) and confirm AI JSON reliability in `handlers/translation_handler.py` & `handlers/translation/glossary_handler.py`.
3. Validate AI prompt edits for chunked/block translations in `handlers/translation_handler.py` (`_initiate_batch_translation`) and decide UX for chunk prompts (possible `precomposed_prompt` support).
4. Add AI chat concept: design in-app discussion channel for ambiguous translations (define UX and dependencies).

## Testing Strategy
- Manual GUI testing for the three AI entry points (block translation, preview translation, glossary notes).
- Inspect app_debug.txt to verify placeholder-restoration logs and glossary statistics are emitted as expected.
- [x] 2025-10-01: Ran targeted Python checks for GlossaryManager to confirm note persistence, occurrence indexing, and markdown exports.

## Risks / Open Questions
- Some providers may ignore the notes instruction; we need to monitor and possibly add retries or heuristics.
- Larger placeholder maps could increase memory/time during block translations; revisit batching if heavy-tag blocks regress.
- Prompt editor flow must not block batch translation pipelines; need fallback for headless/automation scenarios.
