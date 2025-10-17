import { $, el } from '../utils/dom.js';
import { state, ui } from '../core/state.js';
import { ensureChoices } from '../core/config.js';
import { applyAnnotationHighlights } from '../render/text_highlight.js';
import { renderLegend } from '../render/legend.js';
import { updatePrimaryButton } from '../core/ui.js';
import { surfaceFormFromSelection } from '../core/helpers.js';

let classChoices = null;

export function openEntityModal(mode = 'create', annoId = null) {
    ui.mode = mode;
    ui.editId = annoId;

    const bd = $('#modal-bd');
    if (!bd) return;
    bd.style.display = 'flex';

    const titleEl = $('#modal-title');
    if (titleEl) titleEl.textContent = (mode === 'edit') ? 'Edit Annotation' : 'Add Entity';

    const labelNode = $('#inp-label');
    if (mode === 'create' && labelNode) labelNode.value = surfaceFormFromSelection();

    // Show/hide the Delete button with explicit display (more robust than CSS class toggles)
    const delBtn = $('#btn-delete');
    if (delBtn) delBtn.style.display = (mode === 'edit') ? 'inline-flex' : 'none';

    // Destroy any previous Choices instance
    if (classChoices) { classChoices.destroy(); classChoices = null; window.classChoices = null; }

    const sel = $('#sel-class');
    if (sel) {
        sel.innerHTML = '';
        for (const cls of Object.keys(state.classes)) {
            sel.appendChild(el('option', { value: cls }, [cls]));
        }
        const Choices = ensureChoices();
        classChoices = new Choices(sel, {
            searchEnabled: true,
            searchPlaceholderValue: 'Search classes…',
            shouldSort: false,
            itemSelectText: '',
            position: 'bottom',
            allowHTML: false
        });

        // Expose for other modules (e.g., semantic chips) to sync the visible UI
        window.classChoices = classChoices;

        sel.addEventListener('change', () => {
            renderAttrFields();
            renderClassDescription();
        });
    }

    if (mode === 'edit') {
        const anno = state.annotations.find(a => a.id === annoId);
        if (labelNode) labelNode.value = anno?.label || '';

        if (sel) {
            const target = anno?.class || '';
            sel.value = target;

            // Keep Choices UI in sync with the underlying <select>
            try {
                if (classChoices && target) {
                    if (typeof classChoices.setValueByChoice === 'function') {
                        classChoices.setValueByChoice(target);
                    } else if (typeof classChoices.setChoiceByValue === 'function') {
                        classChoices.setChoiceByValue(target);
                    }
                }
            } catch { /* ignore */ }
        }

        renderAttrFields(anno?.attrs || {});
        renderClassDescription();
    } else {
        renderAttrFields();
        renderClassDescription();
    }

    const cancelBtn = $('#btn-cancel');
    const confirmBtn = $('#btn-confirm');

    if (cancelBtn) cancelBtn.onclick = closeEntityModal;
    if (confirmBtn) confirmBtn.onclick = confirmSaveAnnotation;
    const delBtn2 = $('#btn-delete');
    if (delBtn2) delBtn2.onclick = deleteAnnotation;
}

export function closeEntityModal() {
    const bd = $('#modal-bd');
    if (bd) bd.style.display = 'none';
}

export function confirmSaveAnnotation() {
    const sel = $('#sel-class');
    const labelNode = $('#inp-label');
    if (!sel) return;

    const klass = sel.value;
    const label = (labelNode?.value.trim() || surfaceFormFromSelection());

    const meta = state.classes[klass] || { attributes: {} };
    const attrs = {};
    for (const [attr, spec] of Object.entries(meta.attributes || {})) {
        const node = document.querySelector(`#attr-${attr}`);
        if (!node) continue;
        const raw = node.value;
        if (raw === '' && spec.nullable) { attrs[attr] = null; continue; }
        if (spec.type === 'number') attrs[attr] = raw === '' ? null : Number(raw);
        else attrs[attr] = raw;
    }

    if (ui.mode === 'create') {
        const { startIdx, endIdx } = state.selection;
        if (startIdx === null || endIdx === null) return;
        const start = Number(document.querySelector(`.token[data-idx="${startIdx}"]`).dataset.start);
        const end = Number(document.querySelector(`.token[data-idx="${endIdx}"]`).dataset.end);
        const anno = {
            id: `T${state.annotations.length + 1}`,
            class: klass,
            label,
            attrs,
            span: { start, end },
            tokenRange: [startIdx, endIdx]
        };
        state.annotations.push(anno);
    } else if (ui.mode === 'edit') {
        const anno = state.annotations.find(a => a.id === ui.editId);
        if (!anno) return;
        anno.class = klass;
        anno.label = label;
        anno.attrs = attrs;
    }

    ui.dirty = true;
    updatePrimaryButton();
    applyAnnotationHighlights();
    renderLegend();
    closeEntityModal();

    const addBtn = $('#btn-add');
    if (addBtn) { addBtn.disabled = true; addBtn.style = ''; }
    state.selection.startIdx = state.selection.endIdx = null;
}

export function deleteAnnotation() {
    if (ui.mode !== 'edit') return;
    const id = ui.editId;
    state.annotations = state.annotations.filter(a => a.id !== id);
    state.relations = state.relations.filter(r => r.subject !== id && r.object !== id);
    ui.dirty = true;
    updatePrimaryButton();
    applyAnnotationHighlights();
    renderLegend();
    closeEntityModal();
}

function renderAttrFields(prefill = {}) {
    const wrap = $('#attrs');
    if (!wrap) return;
    wrap.innerHTML = '';
    const sel = $('#sel-class');
    if (!sel) return;
    const clsName = sel.value;
    const meta = state.classes[clsName];
    if (!meta || !meta.attributes || Object.keys(meta.attributes).length === 0) {
        wrap.appendChild(el('div', { className: 'empty' }, ['No attributes.']));
        return;
    }

    for (const [attr, spec] of Object.entries(meta.attributes)) {
        const field = el('div', { className: 'row', style: 'align-items:center' }, [
            el('label', { style: 'width: 160px; color: var(--muted);' }, [attr]),
        ]);

        let input;
        if (spec.enum) {
            input = el('select', { id: `attr-${attr}`, style: 'margin-top:5px' },
                spec.enum.map(v => el('option', { value: v }, [v]))
            );
            if (spec.nullable) input.prepend(el('option', { value: '', textContent: '(none)' }));
        } else if (spec.type === 'number') {
            input = el('input', { id: `attr-${attr}`, type: 'number', step: 'any', placeholder: 'num', style: 'margin-top:5px;width:100px' });
        } else {
            input = el('input', { id: `attr-${attr}`, type: 'text', placeholder: 'text' });
        }

        const val = prefill[attr];
        if (val !== undefined && val !== null) input.value = String(val);
        else if (val === null && spec.nullable) input.value = '';

        field.appendChild(input);
        wrap.appendChild(field);
    }
}

function renderClassDescription() {
    const sel = $('#sel-class');
    const descEl = $('#class-desc');
    if (!sel || !descEl) return;
    const clsName = sel.value;
    const meta = state.classes[clsName];
    descEl.textContent = (meta && meta.description) ? meta.description : '(no description)';
}
