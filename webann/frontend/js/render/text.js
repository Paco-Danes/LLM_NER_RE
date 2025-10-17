import { $, $$, el } from '../utils/dom.js';
import { state, ui } from '../core/state.js';
import { tokenizeWithOffsets } from '../tokens/tokenize.js';
import { applyAnnotationHighlights } from './text_highlight.js';

export function renderText() {
    const wrap = $('#text');
    if (!wrap || !state.current) return;
    wrap.innerHTML = '';
    state.tokens = tokenizeWithOffsets(state.current.text);

    state.tokens.forEach((t, idx) => {
        if (t.isSpace) {
            wrap.appendChild(document.createTextNode(t.text));
        } else {
            const span = el('span', {
                className: 'token',
                dataset: { idx: String(idx), start: String(t.start), end: String(t.end), selected: 'false' }
            }, [t.text]);
            wrap.appendChild(span);
        }
    });

    $('#text').addEventListener('mousedown', onMouseDown);
    window.addEventListener('mouseup', onMouseUp);
    $('#text').addEventListener('mousemove', onMouseMove);

    applyAnnotationHighlights();
}

function onMouseDown(e) {
    const node = e.target.closest('.token');
    if (!node) return;
    ui.dragging = true;
    const idx = Number(node.dataset.idx);
    state.selection.startIdx = idx;
    state.selection.endIdx = idx;
    updateSelectionHighlight();
}

function onMouseMove(e) {
    if (!ui.dragging) return;
    const node = e.target.closest('.token');
    if (!node) return;
    const idx = Number(node.dataset.idx);
    state.selection.endIdx = idx;
    if (state.selection.endIdx < state.selection.startIdx) {
        [state.selection.startIdx, state.selection.endIdx] = [state.selection.endIdx, state.selection.startIdx];
    }
    updateSelectionHighlight();
}

function onMouseUp() {
    if (!ui.dragging) return;
    ui.dragging = false;
    const { startIdx, endIdx } = state.selection;
    const hasSel = startIdx !== null && endIdx !== null;
    const addBtn = $('#btn-add');
    if (addBtn) {
        addBtn.disabled = !hasSel;
        addBtn.style = hasSel ? 'border-color: #7aa2f791' : '';
    }
}

export function clearSelection() {
    state.selection.startIdx = state.selection.endIdx = null;
    updateSelectionHighlight();
    const addBtn = $('#btn-add');
    if (addBtn) { addBtn.disabled = true; addBtn.style = ''; }
}

export function updateSelectionHighlight() {
    $$('.token').forEach(s => s.dataset.selected = 'false');
    const { startIdx, endIdx } = state.selection;
    if (startIdx === null || endIdx === null) return;
    for (let i = startIdx; i <= endIdx; i++) {
        const node = document.querySelector(`.token[data-idx="${i}"]`);
        if (node) node.dataset.selected = 'true';
    }
}

document.addEventListener('keydown', (e) => { if (e.key === 'Escape') clearSelection(); });
