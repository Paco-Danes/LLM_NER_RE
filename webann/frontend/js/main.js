import { includePartials } from '/lib/includes.js';
import { $ } from './utils/dom.js';
import { state, ui } from './core/state.js';
import { API } from './api/index.js';
import { renderText, clearSelection } from './render/text.js';
import { renderLegend } from './render/legend.js';
import { renderRelationships, validateRelations } from './render/relations.js';
import { setStatus, updatePrimaryButton } from './core/ui.js';
import { buildAnnotationPayload, spanToTokenRange } from './core/helpers.js';
import { openOverwriteModal, openDeleteAllModal } from './modals/common.js';
import { openEntityModal } from './modals/entity.js';
import { initRouter } from './router/index.js';
import { wireSemanticButtons } from './semantic/index.js';
import { applyAnnotationHighlights } from './render/text_highlight.js';

async function loadTextResponse(data) {
    state.current = { id: data.id, text: data.text };
    state.texts.cursor = data.cursor;
    state.texts.total = data.total;

    state.annotations = [];
    clearSelection();

    state.saved.exists = false;
    state.saved.wasEmpty = false;
    const emptyNote = $('#empty-annot-note');
    if (emptyNote) emptyNote.style.display = 'none';

    renderText();

    try {
        const saved = await API.getAnnotation(state.current.id);
        if (saved && Array.isArray(saved.entities)) {
            state.saved.exists = true;
            state.saved.wasEmpty = saved.entities.length === 0;
            if (emptyNote && state.saved.wasEmpty) emptyNote.style.display = 'block';

            const annos = [];
            for (const ent of saved.entities) {
                const tr = spanToTokenRange(ent.span);
                if (!tr) continue;
                annos.push({
                    id: ent.id,
                    class: ent.class,
                    label: ent.label,
                    attrs: ent.attributes || {},
                    span: { start: ent.span.start, end: ent.span.end },
                    tokenRange: tr
                });
            }
            state.annotations = annos;

            // make them visible immediately
            applyAnnotationHighlights();
            setStatus(`Doc ${data.cursor + 1} / ${data.total} (loaded saved annotations)`);
        } else {
            setStatus(`Doc ${data.cursor + 1} / ${data.total}`);
        }

        state.relations = [];
        if (saved && Array.isArray(saved.relations)) {
            const ids = new Set(state.annotations.map(a => a.id));
            for (const r of saved.relations) {
                if (ids.has(r.subject) && ids.has(r.object)) {
                    const keys = Object.keys(r.attributes || {});
                    const subjectOrder = keys.filter(k => k.startsWith('subject_'));
                    const objectOrder = keys.filter(k => k.startsWith('object_'));
                    const statementOrder = keys.filter(k => k !== 'edge_predicate' && !k.startsWith('subject_') && !k.startsWith('object_'));
                    state.relations.push({
                        id: r.id,
                        predicate: r.predicate || null,
                        subject: r.subject,
                        object: r.object,
                        attrs: r.attributes || {},
                        attrOrder: { subject: subjectOrder, object: objectOrder, statement: statementOrder }
                    });
                }
            }
        }
    } catch {
        setStatus(`Doc ${data.cursor + 1} / ${data.total}`);
    }

    renderLegend();
    renderRelationships();
    ui.dirty = false;
    updatePrimaryButton();
}

function wireRelationsDropzone() {
    const relDrop = $('#rels-drop');
    if (!relDrop) return;
    relDrop.addEventListener('dragover', (e) => { e.preventDefault(); relDrop.classList.add('dragover'); });
    relDrop.addEventListener('dragleave', () => relDrop.classList.remove('dragover'));
    relDrop.addEventListener('drop', (e) => {
        e.preventDefault(); relDrop.classList.remove('dragover');
        const entId = e.dataTransfer.getData('text/plain');
        if (!entId) return;
        const rel = { id: `R${state.relations.length + 1}`, predicate: null, subject: entId, object: null, attrs: {} };
        state.relations.push(rel);
        ui.dirty = true; updatePrimaryButton();
        renderRelationships();
    });
}

async function boot() {
    // Load partials first
    await includePartials();

    // Router must be ready BEFORE we dispatch the event so it can bind buttons
    initRouter();
    document.dispatchEvent(new Event('partials:loaded'));

    // Backend bootstrap
    state.classes = await API.getClasses();
    state.relationsMeta = await API.getRelations();

    const first = await API.getNextText(null);
    await loadTextResponse(first);

    wireSemanticButtons();
    wireRelationsDropzone();

    // Buttons
    $('#btn-add')?.addEventListener('click', () => openEntityModal('create'));
    $('#btn-prev')?.addEventListener('click', async () => {
        const data = await API.getPrevText(Math.max(0, state.texts.cursor - 1));
        await loadTextResponse(data);
    });
    // NEW: clear selection button
    $('#btn-clear')?.addEventListener('click', () => clearSelection());

    $('#btn-delete-all')?.addEventListener('click', () => {
        if (!state.annotations.length) return;
        openDeleteAllModal(() => {
            state.annotations = [];
            state.relations = [];
            ui.dirty = true;
            updatePrimaryButton();
            renderText();
            renderLegend();
            renderRelationships();
            setStatus('All annotations cleared.');
        }, () => setStatus('Delete all canceled.'));
    });

    $('#btn-save')?.addEventListener('click', async () => {
        try {
            const shouldSkip = state.saved.exists && !ui.dirty;
            if (shouldSkip) {
                setStatus('Skipping…');
                const data = await API.getNextText(state.texts.cursor + 1);
                await loadTextResponse(data);
                return;
            }

            if (!validateRelations()) {
                setStatus('Please complete highlighted relationships before saving.');
                return;
            }

            const payload = buildAnnotationPayload();
            const existing = await API.getAnnotation(payload.text_id);

            const proceedSave = async (overwrite) => {
                await API.saveAnnotations(payload, overwrite);
                ui.dirty = false; updatePrimaryButton();
                setStatus('Saved. Loading next text…');
                const data = await API.getNextText(state.texts.cursor + 1);
                await loadTextResponse(data);
            };

            if (existing && Array.isArray(existing.entities) && existing.entities.length > 0) {
                openOverwriteModal(() => proceedSave(true), () => setStatus('Save canceled.'));
            } else {
                await proceedSave(!!existing);
            }
        } catch (e) {
            alert('Save failed: ' + (e.message || String(e)));
        }
    });

    setStatus('Ready.');
}

boot().catch(err => {
    console.error(err);
    setStatus('Failed to initialize front-end.');
});
