import { $ } from '../utils/dom.js';
import { state, ui } from './state.js';

export function setStatus(msg) {
    const el = $('#status');
    if (el) el.textContent = msg;
}

export function updatePrimaryButton() {
    const btn = $('#btn-save');
    if (!btn) return;
    const shouldSkip = state.saved.exists && !ui.dirty;
    btn.textContent = shouldSkip ? 'Skip ▶' : 'Save & Next ▶';
    btn.disabled = false;
}
