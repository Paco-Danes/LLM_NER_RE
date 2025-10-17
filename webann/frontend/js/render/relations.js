import { $, el } from '../utils/dom.js';
import { state } from '../core/state.js';
import { classColor } from '../utils/colors.js';
import { entityById } from '../core/helpers.js';
import { openRelationModal } from '../modals/relation.js';

export function getAllowedRelationNames(leftClass, rightClass = null) {
    const out = [];
    for (const name of Object.keys(state.relationsMeta)) {
        if (relationAllowedBidirectional(leftClass, rightClass, name)) out.push(name);
    }
    return out;
}

export function relationOrientationForPair(relName, leftClass, rightClass) {
    const spec = state.relationsMeta[relName];
    if (!spec || !leftClass || !rightClass) return null;
    const fwd = spec.subject?.includes(leftClass) && spec.object?.includes(rightClass);
    const rev = spec.subject?.includes(rightClass) && spec.object?.includes(leftClass);
    if (fwd && !rev) return 'forward';
    if (rev && !fwd) return 'reverse';
    if (fwd && rev) return 'both';
    return null;
}

export function firstEntityRoleFor(relName, klass) {
    const spec = state.relationsMeta[relName];
    if (!spec) return null;
    const subjOk = spec.subject?.includes(klass);
    const objOk = spec.object?.includes(klass);
    if (subjOk && !objOk) return 'subject';
    if (!subjOk && objOk) return 'object';
    if (subjOk && objOk) return 'either';
    return null;
}

export function renderRelationships() {
    const list = $('#rels-list');
    const dz = $('#rels-drop');
    if (!list || !dz) return;

    list.innerHTML = '';

    for (const r of state.relations) {
        list.appendChild(relRowDOM(r));
    }

    dz.classList.remove('dragover');
    dz.style.display = '';
    list.after(dz);

    dz.textContent = 'Drag an entity chip from the left to start';
}

export function validateRelations() {
    let ok = true;
    for (const r of state.relations) {
        const row = document.querySelector(`.rel-row[data-rel-id="${r.id}"]`);
        const highlight = (msg) => {
            ok = false;
            if (row) {
                row.classList.add('invalid');
                const err = row.querySelector('.rel-error');
                if (err) {
                    err.textContent = msg || 'Incomplete relation';
                    err.classList.add('show');
                    setTimeout(() => err.classList.remove('show'), 3000);
                }
                setTimeout(() => row.classList.remove('invalid'), 900);
            }
        };

        if (!r.subject || !r.object || !r.predicate || r.predicate.trim() === '') {
            highlight('Relation needs subject, type, and object');
            continue;
        }

        const spec = state.relationsMeta[r.predicate];
        if (!spec) { highlight('Unknown relation'); continue; }
        const left = entityById(r.subject);
        const right = entityById(r.object);
        if (!left || !right) { highlight('Dangling entity reference'); continue; }

        const fwd = spec.subject?.includes(left.class) && spec.object?.includes(right.class);
        const rev = spec.subject?.includes(right.class) && spec.object?.includes(left.class);
        if (!fwd && !rev) { highlight('Classes not allowed for this relation'); continue; }

        const attrs = spec.attributes || {};
        for (const [name, aspec] of Object.entries(attrs)) {
            const v = (r.attrs || {})[name];

            if ((v === undefined || v === null || v === '') && aspec.nullable === false) {
                highlight(`Missing required attribute: ${name}`);
                break;
            }
            if (v === null || v === '' || v === undefined) continue;

            if (aspec.kind === 'enum') {
                if (!aspec.enum.includes(v)) { highlight(`'${name}' has invalid value`); break; }
            } else if (aspec.kind === 'number') {
                if (Number.isNaN(Number(v))) { highlight(`'${name}' must be a number`); break; }
            } else if (aspec.kind === 'entity') {
                const ent = entityById(v);
                if (!ent || !aspec.classes.includes(ent.class)) {
                    highlight(`'${name}' must refer to a ${aspec.classes.join(' or ')}`);
                    break;
                }
            }
        }
    }
    return ok;
}

function relationAllowedBidirectional(leftClass, rightClass, relName) {
    const spec = state.relationsMeta[relName];
    if (!spec) return false;
    if (!leftClass && !rightClass) return true;
    if (leftClass && !rightClass) {
        return (spec.subject?.includes(leftClass) || spec.object?.includes(leftClass));
    }
    if (!leftClass && rightClass) {
        return (spec.subject?.includes(rightClass) || spec.object?.includes(rightClass));
    }
    const fwd = spec.subject?.includes(leftClass) && spec.object?.includes(rightClass);
    const rev = spec.subject?.includes(rightClass) && spec.object?.includes(leftClass);
    return !!(fwd || rev);
}

function relRowDOM(rel) {
    const leftEnt = rel.subject ? entityById(rel.subject) : null;
    const rightEnt = rel.object ? entityById(rel.object) : null;

    const makeChip = (ent) => {
        const colors = classColor(ent.class);
        return el('span', { className: 'rel-chip', style: `background:${colors.chip}; border-color:${colors.border}` },
            [`${ent.label} (${ent.class})`]);
    };

    const makePlaceholder = (side) => {
        const ph = el('span', { className: 'rel-placeholder', textContent: side === 'subject' ? 'drop subject here' : 'drop object here' });
        ph.addEventListener('dragover', (e) => { e.preventDefault(); ph.classList.add('dragover'); });
        ph.addEventListener('dragleave', () => ph.classList.remove('dragover'));
        ph.addEventListener('drop', (e) => {
            e.preventDefault(); ph.classList.remove('dragover');
            const entId = e.dataTransfer.getData('text/plain');
            if (!entId) return;
            if ((side === 'subject' && rel.object === entId) || (side === 'object' && rel.subject === entId)) return;
            const ent = entityById(entId);
            if (!ent) return;
            if (rel.predicate) {
                const spec = state.relationsMeta[rel.predicate];
                const ok = side === 'subject' ? spec.subject?.includes(ent.class) : spec.object?.includes(ent.class);
                if (!ok) return;
            }
            if (side === 'subject') rel.subject = entId; else rel.object = entId;
            const rowNode = document.querySelector(`.rel-row[data-rel-id="${rel.id}"]`);
            if (rowNode) rowNode.classList.remove('invalid');
            renderRelationships();
        });
        return ph;
    };

    const relBtnLabel = rel.predicate ? rel.predicate : 'Select relation';
    const relBtn = el('button', { className: 'rel-btn ' + (rel.predicate ? 'as-chip' : ''), textContent: relBtnLabel });
    relBtn.onclick = () => openRelationModal(rel.id);

    const x = el('button', { className: 'rel-x', textContent: '✕', title: 'Remove relation' });
    x.onclick = () => {
        state.relations = state.relations.filter(r => r.id !== rel.id);
        renderRelationships();
    };

    const row = el('div', { className: 'rel-row', dataset: { relId: rel.id } });
    row.appendChild(leftEnt ? makeChip(leftEnt) : makePlaceholder('subject'));
    row.appendChild(el('span', { textContent: ' — ' }));
    row.appendChild(relBtn);
    row.appendChild(el('span', { textContent: ' — ' }));
    row.appendChild(rightEnt ? makeChip(rightEnt) : makePlaceholder('object'));
    row.appendChild(x);
    row.appendChild(el('span', { className: 'rel-error', 'aria-live': 'polite' }, []));
    return row;
}
