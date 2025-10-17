import { $, el } from '../utils/dom.js';
import { state, ui } from '../core/state.js';
import { ensureChoices } from '../core/config.js';
import { getAllowedRelationNames, relationOrientationForPair, firstEntityRoleFor, renderRelationships } from '../render/relations.js';
import { entityById } from '../core/helpers.js';
import { API } from '../api/index.js';

let relChoices = null;

export function openRelationModal(relId) {
    ui.relEditingId = relId;
    const rel = state.relations.find(r => r.id === relId);
    if (!rel) return;

    const left = rel.subject ? entityById(rel.subject) : null;
    const right = rel.object ? entityById(rel.object) : null;

    const bd = $('#rel-modal-bd');
    if (!bd) return;
    bd.style.display = 'flex';

    const title = `Select Relation (${left ? left.class : '?'} ↔ ${right ? right.class : '?'})`;
    const titleEl = $('#rel-modal-title');
    if (titleEl) titleEl.textContent = title;

    const sel = $('#sel-rel');
    if (!sel) return;
    sel.innerHTML = '';
    const allowed = getAllowedRelationNames(left?.class || null, right?.class || null);
    allowed.forEach(name => sel.appendChild(el('option', { value: name }, [name])));

    if (relChoices) { relChoices.destroy(); relChoices = null; }
    const Choices = ensureChoices();
    relChoices = new Choices(sel, { searchEnabled: true, shouldSort: false, itemSelectText: '', position: 'bottom', allowHTML: false });

    if (rel.predicate && allowed.includes(rel.predicate)) {
        relChoices.setChoiceByValue(rel.predicate);
        sel.value = rel.predicate;
    }

    renderRelAttrFields(sel.value, rel.attrs || {}, rel.attrOrder || null);
    renderRelDescription(sel.value);

    sel.addEventListener('change', () => {
        renderRelAttrFields(sel.value, {}, null);
        renderRelDescription(sel.value);
    });

    API.semanticStatus('relation').then(s => {
        const b = $('#btn-rel-find');
        if (!b) return;
        b.disabled = !(s.ready && s.has_embedder && s.size > 0);
        b.title = b.disabled ? 'Semantic index not ready' : 'Semantic search relations';
    });

    const btnDel = $('#btn-rel-delete');
    if (btnDel) {
        btnDel.style.display = 'inline-flex';
        btnDel.onclick = () => {
            state.relations = state.relations.filter(r => r.id !== rel.id);
            bd.style.display = 'none';
            renderRelationships();
        };
    }

    $('#btn-rel-cancel')?.addEventListener('click', () => closeRelationModal(), { once: true });
    $('#btn-rel-confirm')?.addEventListener('click', () => confirmRelation(), { once: true });
    $('#btn-rel-find')?.addEventListener('click', () => findRelationSuggestions(), { once: true });
}

export function closeRelationModal() {
    const bd = $('#rel-modal-bd');
    if (bd) bd.style.display = 'none';
}

function confirmRelation() {
    const rel = state.relations.find(r => r.id === ui.relEditingId);
    if (!rel) return;

    const name = $('#sel-rel').value;
    rel.predicate = name;

    const left = rel.subject ? entityById(rel.subject) : null;
    const right = rel.object ? entityById(rel.object) : null;

    if (left && right) {
        const ori = relationOrientationForPair(name, left.class, right.class);
        if (ori === 'reverse') {
            const tmp = rel.subject; rel.subject = rel.object; rel.object = tmp;
        }
    } else if (left && !right) {
        const role = firstEntityRoleFor(name, left.class);
        if (role === 'object') { rel.object = rel.subject; rel.subject = null; }
    } else if (!left && right) {
        const role = firstEntityRoleFor(name, right.class);
        if (role === 'subject') { rel.subject = rel.object; rel.object = null; }
    }

    const spec = state.relationsMeta[name] || { attributes: {} };
    const out = {};

    const subjectRows = Array.from(document.querySelectorAll('#rel-attrs-subj .row'));
    const objectRows = Array.from(document.querySelectorAll('#rel-attrs-obj .row'));
    const stmtRows = Array.from(document.querySelectorAll('#rel-attrs-stmt .row'));

    function pushRows(rows) {
        for (const r of rows) {
            const attr = r.dataset.attr;
            const aspec = (spec.attributes || {})[attr];
            if (!aspec) continue;
            const node = r.querySelector(`#rel-attr-${attr}`);
            if (!node) continue;
            const raw = node.value;

            if (raw === '' && aspec.nullable) out[attr] = null;
            else if (aspec.kind === 'number') out[attr] = raw === '' ? null : Number(raw);
            else out[attr] = raw;
        }
    }

    pushRows(subjectRows);

    if ((spec.attributes || {}).edge_predicate) {
        const node = document.querySelector('#rel-attr-edge_predicate');
        if (node) out['edge_predicate'] = node.value === '' ? null : node.value;
    }

    pushRows(objectRows);
    pushRows(stmtRows);

    rel.attrOrder = {
        subject: subjectRows.map(r => r.dataset.attr),
        object: objectRows.map(r => r.dataset.attr),
        statement: stmtRows.map(r => r.dataset.attr)
    };
    rel.attrs = out;

    const row = document.querySelector(`.rel-row[data-rel-id="${rel.id}"]`);
    if (row) row.classList.remove('invalid');

    renderRelationships();
    closeRelationModal();
}

function findRelationSuggestions() {
    const btn = $('#btn-rel-find');
    if (!btn) return;
    const rel = state.relations.find(r => r.id === ui.relEditingId);
    if (!rel) return;
    const left = rel.subject ? entityById(rel.subject) : null;
    const right = rel.object ? entityById(rel.object) : null;

    const relSuggestBox = $('#rel-suggest');
    const relSuggestSection = $('#rel-suggest-section');
    if (relSuggestBox) relSuggestBox.innerHTML = '';
    if (relSuggestSection) relSuggestSection.style.display = 'block';

    const inp = document.querySelector('#rel-modal-bd .choices__input--cloned');
    const query = (inp && inp.value.trim()) || '';

    btn.classList.add('loading');
    API.semanticSuggest({
        kind: 'relation',
        query,
        top_k: 10,
        threshold: 0.2,
        subject_class: null,
        object_class: null
    })
        .then(res => {
            const allowed = new Set(getAllowedRelationNames(left?.class || null, right?.class || null));
            const filtered = res.items.filter(it => allowed.has(it.class_name));
            if (relSuggestBox) {
                if (!filtered.length) {
                    relSuggestBox.appendChild(el('span', { className: 'empty' }, ['No semantic suggestions.']));
                } else {
                    for (const it of filtered) {
                        const chip = el('span', { className: 'chip', title: it.description || '' },
                            [it.class_name, ' ', el('small', {}, [`${Math.round(it.score * 100)}%`])]
                        );
                        chip.addEventListener('click', () => {
                            if (relChoices) relChoices.setChoiceByValue(it.class_name);
                            $('#sel-rel').value = it.class_name;
                            $('#sel-rel').dispatchEvent(new Event('change'));
                        });
                        relSuggestBox.appendChild(chip);
                    }
                }
            }
        })
        .catch(e => alert('Semantic search failed: ' + e.message))
        .finally(() => btn.classList.remove('loading'));
}

function renderRelDescription(relName) {
    const spec = state.relationsMeta[relName];
    const elDesc = $('#rel-desc');
    if (!elDesc) return;
    elDesc.textContent = (spec && spec.description) ? spec.description : '(no description)';
}

function classifyAttrName(name) {
    if (name === 'edge_predicate') return 'predicate';
    if (name.startsWith('subject_')) return 'subject';
    if (name.startsWith('object_')) return 'object';
    return 'statement';
}

function splitSpecOrder(attrs) {
    const groups = { subject: [], predicate: [], object: [], statement: [] };
    for (const n of Object.keys(attrs)) groups[classifyAttrName(n)].push(n);
    return groups;
}

function wireRelAttrSorting(container) {
    let dragRow = null;

    container.querySelectorAll('.row .drag-handle').forEach(handle => {
        const row = handle.closest('.row');
        handle.addEventListener('mousedown', () => {
            row.setAttribute('draggable', 'true'); row.style.opacity = '0.7';
        });
        handle.addEventListener('mouseup', () => {
            row.removeAttribute('draggable'); row.style.opacity = '';
        });
    });

    container.addEventListener('dragstart', (e) => {
        const row = e.target.closest('.row');
        if (!row || !row.hasAttribute('draggable')) { e.preventDefault(); return; }
        dragRow = row;
        e.dataTransfer.effectAllowed = 'move';
    });

    container.addEventListener('dragover', (e) => {
        if (!dragRow) return;
        e.preventDefault();
        const after = getRowAfterPosition(container, e.clientY);
        if (after == null) container.appendChild(dragRow);
        else container.insertBefore(dragRow, after);
    });

    container.addEventListener('drop', () => {
        if (!dragRow) return;
        dragRow.removeAttribute('draggable'); dragRow.style.opacity = ''; dragRow = null;
    });

    container.addEventListener('dragend', () => {
        if (dragRow) {
            dragRow.removeAttribute('draggable'); dragRow.style.opacity = ''; dragRow = null;
        }
    });

    function getRowAfterPosition(container, y) {
        const rows = [...container.querySelectorAll('.row')].filter(r => r !== dragRow);
        let closest = null; let closestOffset = Number.NEGATIVE_INFINITY;
        for (const r of rows) {
            const rect = r.getBoundingClientRect();
            const offset = y - rect.top - rect.height / 2;
            if (offset < 0 && offset > closestOffset) {
                closestOffset = offset; closest = r;
            }
        }
        return closest;
    }
}

function updateRelAttrContextLabelsGroup(container) {
    const rows = [...container.querySelectorAll('.row')];
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const labelEl = row.querySelector('.label-txt');
        const base = labelEl.dataset.base;
        if (base === 'edge_predicate') { labelEl.textContent = base; continue; }
        const m = /^(subject|object)_(.+)$/.exec(base);
        if (!m || i === 0) { labelEl.textContent = base; continue; }

        const prevInput = rows[i - 1].querySelector('select, input');
        let prefix = '';
        if (prevInput) {
            if (prevInput.tagName === 'SELECT') {
                const opt = prevInput.options[prevInput.selectedIndex];
                prefix = opt ? opt.textContent.trim() : '';
            } else {
                prefix = (prevInput.value || '').trim();
            }
            prefix = prefix.replace(/\s*\([^)]*\)\s*$/, '');
        }
        if (prefix) {
            const suffix = m[2];
            labelEl.innerHTML = '';
            labelEl.appendChild(el('span', { style: 'color:#55b5ff;font-weight:600' }, [prefix]));
            labelEl.appendChild(document.createTextNode('_' + suffix));
        } else {
            labelEl.textContent = base;
        }
    }
}

function buildPredicateFixedRow(aspec, value) {
    const row = el('div', { className: 'row', style: 'align-items:center;gap:10px;' });
    const label = el('label', { className: 'rel-attr-label', style: 'width: 200px; color: var(--muted); display:flex; gap:4px; align-items:center;' },
        [el('span', { className: 'label-txt', dataset: { base: 'edge_predicate' } }, ['edge_predicate'])]
    );
    let input;
    if (aspec && aspec.kind === 'enum') {
        input = el('select', { id: `rel-attr-edge_predicate` }, aspec.enum.map(v => el('option', { value: v }, [v])));
        if (aspec.nullable) {
            input.insertBefore(el('option', { value: '', textContent: '(none)' }), input.firstChild);
            if (value === undefined || value === null || value === '') input.value = '';
            else input.value = String(value);
        } else if (value !== undefined && value !== null) {
            input.value = String(value);
        }
    } else {
        input = el('input', { id: `rel-attr-edge_predicate`, type: 'text' });
        if (value !== undefined && value !== null) input.value = String(value);
    }
    row.appendChild(el('span', { style: 'width:18px' }, []));
    row.appendChild(label);
    row.appendChild(input);
    return row;
}

function buildRelAttrRow(attr, aspec, value) {
    const row = el('div', { className: 'row', style: 'align-items:center;gap:10px;', dataset: { attr } });
    const handle = el('span', { className: 'drag-handle', title: 'Drag to reorder', style: 'cursor:grab;user-select:none;padding:0 6px;font-size:18px;line-height:1;color:var(--muted);' }, ['⋮⋮']);
    const label = el('label', { className: 'rel-attr-label', style: 'width: 200px; color: var(--muted); display:flex; gap:4px; align-items:center;' },
        [el('span', { className: 'label-txt', dataset: { base: attr } }, [attr])]
    );
    let input = null;
    const val = value;

    if (aspec.kind === 'enum') {
        input = el('select', { id: `rel-attr-${attr}` }, aspec.enum.map(v => el('option', { value: v }, [v])));
        if (aspec.nullable) {
            input.insertBefore(el('option', { value: '', textContent: '(none)' }), input.firstChild);
            if (val === undefined || val === null || val === '') input.value = '';
            else input.value = String(val);
        } else if (val !== undefined && val !== null) {
            input.value = String(val);
        }
    } else if (aspec.kind === 'number') {
        input = el('input', { id: `rel-attr-${attr}`, type: 'number', step: 'any', style: 'width:120px' });
        if (val !== undefined && val !== null) input.value = String(val);
    } else if (aspec.kind === 'entity') {
        const classes = aspec.classes || [];
        const ids = new Set(state.annotations.filter(a => classes.includes(a.class)).map(a => a.id));
        input = el('select', { id: `rel-attr-${attr}` }, []);
        if (aspec.nullable) input.appendChild(el('option', { value: '', textContent: '(none)' }));
        if (!ids.size) {
            input.disabled = true;
            input.appendChild(el('option', { value: '', textContent: 'No matching entities in document' }));
        } else {
            for (const ent of state.annotations) {
                if (!ids.has(ent.id)) continue;
                const labelTxt = `${ent.label} (${ent.class})`;
                input.appendChild(el('option', { value: ent.id, textContent: labelTxt }));
            }
        }
        if (val === undefined || val === null || val === '') {
            if (aspec.nullable) input.value = '';
        } else {
            input.value = String(val);
        }
    } else {
        input = el('input', { id: `rel-attr-${attr}`, type: 'text' });
        if (val !== undefined && val !== null) input.value = String(val);
    }

    row.appendChild(handle);
    row.appendChild(label);
    row.appendChild(input);
    return row;
}

function renderRelAttrFields(relName, prefill = {}, orders = null) {
    const wrap = $('#rel-attrs');
    if (!wrap) return;
    wrap.innerHTML = '';

    const spec = state.relationsMeta[relName];
    if (!spec) { wrap.appendChild(el('div', { className: 'empty' }, ['No attributes.'])); return; }
    const attrs = spec.attributes || {};

    const specGroups = splitSpecOrder(attrs);
    const recovered = { subject: [], object: [], statement: [] };

    if (prefill && Object.keys(prefill).length) {
        for (const k of Object.keys(prefill)) {
            const g = classifyAttrName(k);
            if (g === 'subject') recovered.subject.push(k);
            else if (g === 'object') recovered.object.push(k);
            else if (g === 'statement') recovered.statement.push(k);
        }
        for (const g of ['subject', 'object', 'statement']) {
            for (const k of specGroups[g]) if (!recovered[g].includes(k)) recovered[g].push(k);
        }
    }

    const useOrders = orders && (orders.subject || orders.object || orders.statement)
        ? {
            subject: (orders.subject || []).filter(n => attrs[n]).concat(specGroups.subject.filter(n => !(orders.subject || []).includes(n))),
            object: (orders.object || []).filter(n => attrs[n]).concat(specGroups.object.filter(n => !(orders.object || []).includes(n))),
            statement: (orders.statement || []).filter(n => attrs[n]).concat(specGroups.statement.filter(n => !(orders.statement || []).includes(n))),
        }
        : (Object.keys(prefill).length ? recovered : specGroups);

    const subjBox = el('div', { id: 'rel-attrs-subj', className: 'rel-attrs-group' });
    const objBox = el('div', { id: 'rel-attrs-obj', className: 'rel-attrs-group' });
    const stmtBox = el('div', { id: 'rel-attrs-stmt', className: 'rel-attrs-group' });

    const hr = () => el('div', { className: 'rel-attrs-sep', style: 'height:1px;background:var(--border);margin:6px 0;' });
    const hrStmt = () => el('div', { className: 'rel-attrs-sep', style: 'height:1px;border-top:1px dashed #5b74a9be;margin:6px 0;' });

    for (const attr of useOrders.subject) {
        const aspec = attrs[attr]; if (!aspec) continue;
        if (aspec.kind === 'entity') {
            const classes = aspec.classes || [];
            const cands = state.annotations.filter(a => classes.includes(a.class));
            if (cands.length === 0 && aspec.nullable !== false) continue;
        }
        subjBox.appendChild(buildRelAttrRow(attr, aspec, prefill[attr]));
    }
    wrap.appendChild(subjBox);

    const hasPred = specGroups.predicate.includes('edge_predicate');
    if (hasPred) {
        wrap.appendChild(hr());
        wrap.appendChild(buildPredicateFixedRow(attrs['edge_predicate'], prefill['edge_predicate']));
        wrap.appendChild(hr());
    } else {
        wrap.appendChild(hr());
    }

    for (const attr of useOrders.object) {
        const aspec = attrs[attr]; if (!aspec) continue;
        if (aspec.kind === 'entity') {
            const classes = aspec.classes || [];
            const cands = state.annotations.filter(a => classes.includes(a.class));
            if (cands.length === 0 && aspec.nullable !== false) continue;
        }
        objBox.appendChild(buildRelAttrRow(attr, aspec, prefill[attr]));
    }
    wrap.appendChild(objBox);

    const anyStmt = useOrders.statement.some(n => attrs[n]);
    if (anyStmt) wrap.appendChild(hrStmt());

    for (const attr of useOrders.statement) {
        const aspec = attrs[attr]; if (!aspec) continue;
        stmtBox.appendChild(buildRelAttrRow(attr, aspec, prefill[attr]));
    }
    if (anyStmt) wrap.appendChild(stmtBox);

    wireRelAttrSorting(subjBox);
    wireRelAttrSorting(objBox);
    wireRelAttrSorting(stmtBox);

    const refresh = () => {
        updateRelAttrContextLabelsGroup(subjBox);
        updateRelAttrContextLabelsGroup(objBox);
        updateRelAttrContextLabelsGroup(stmtBox);
    };
    refresh();
    wrap.addEventListener('change', (e) => {
        if (e.target && (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT')) refresh();
    });
}
