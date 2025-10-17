import { $, $$, el } from '../utils/dom.js';
import { API } from '../api/index.js';
import { ensureChoices } from '../core/config.js';

let loaded = false;
let enumsCache = {};
let generalQualifiers = {};

export async function showProposeRelationPage() {
    let overlay = $('#propose-rel-overlay');
    if (!overlay) {
        overlay = el('div', { id: 'propose-rel-overlay', className: 'page-overlay', style: 'display:none' });
        $('.main')?.appendChild(overlay);
    }
    if (!loaded) {
        const html = await (await fetch('/partials/propose-relation.html')).text();
        overlay.innerHTML = html;
        loaded = true;
        await init();
    }
    overlay.style.display = 'block';
    $('#propose-rel-status').textContent = 'Fill out the relation and click Save.';
    if (location.hash !== '#/propose-relation') location.hash = '#/propose-relation';
}

export function hideProposeRelationPage() {
    const overlay = $('#propose-rel-overlay');
    if (overlay) overlay.style.display = 'none';
    if (location.hash === '#/propose-relation') history.replaceState(null, '', ' ');
}

async function init() {
    const status = $('#propose-rel-status');
    const list = $('#pr-attr-list');
    const subjSel = $('#pr-subject');
    const objSel = $('#pr-object');
    const predsInp = $('#pr-preds');

    const classesRes = await API.getClasses();
    const allClasses = Object.keys(classesRes || {});
    subjSel.innerHTML = ''; objSel.innerHTML = '';
    allClasses.forEach(c => {
        subjSel.appendChild(el('option', { value: c, textContent: c }));
        objSel.appendChild(el('option', { value: c, textContent: c }));
    });

    const Choices = ensureChoices();
    const subjChoices = new Choices(subjSel, { removeItemButton: true, shouldSort: true, itemSelectText: '' });
    const objChoices = new Choices(objSel, { removeItemButton: true, shouldSort: true, itemSelectText: '' });

    const qualDatalist = $('#pr-qual-suggestions');

    const refreshEnumOptions = async () => {
        enumsCache = await API.getEnums();
        $$('#pr-attr-list select[data-role="enum-select"]').forEach(sel => {
            const current = sel.value;
            sel.innerHTML = '';
            sel.appendChild(el('option', { value: '', textContent: '(choose enum)' }));
            Object.keys(enumsCache).forEach(n =>
                sel.appendChild(el('option', { value: n, textContent: n }))
            );
            if (current && enumsCache[current]) sel.value = current;
        });
    };

    const fd = await API.getFieldDescriptions();
    generalQualifiers = (fd && fd.general_qualifiers) ? fd.general_qualifiers : {};
    qualDatalist.innerHTML = '';
    Object.keys(generalQualifiers).forEach(k => qualDatalist.appendChild(el('option', { value: k })));

    await refreshEnumOptions();

    const addFieldRow = (prefill = {}) => {
        const row = el('div', { className: 'attr-row pr-grid' });

        const name = el('input', { type: 'text', placeholder: 'subject_direction', value: prefill.name || '' });
        name.setAttribute('list', 'pr-qual-suggestions');
        name.pattern = '^[a-z_][a-z0-9_]*$';

        const type = el('select', {});
        ['fixed', 'dynamic', 'free_text'].forEach(t => type.appendChild(el('option', { value: t, textContent: t })));
        type.value = prefill.kind || 'fixed';

        const cfg = el('div', { className: 'stack' });

        const optWrap = el('label', { className: 'chk-wrap', title: 'Optional field' });
        const opt = el('input', { type: 'checkbox' });
        opt.checked = (prefill.optional !== undefined) ? !!prefill.optional : true;
        optWrap.appendChild(opt);

        const desc = el('textarea', { rows: 2, className: 'whitebox', placeholder: 'Field description', value: prefill.description || '' });

        const del = el('button', { type: 'button', className: 'ghost', textContent: '✕', title: 'Remove field' });
        del.onclick = () => row.remove();

        const buildFixed = () => {
            cfg.innerHTML = '';
            const enumSel = el('select', { className: 'w100', dataset: { role: 'enum-select' } });
            enumSel.appendChild(el('option', { value: '', textContent: '(choose enum)' }));
            Object.keys(enumsCache || {}).forEach(n => enumSel.appendChild(el('option', { value: n, textContent: n })));
            if (prefill.enum_name) enumSel.value = prefill.enum_name;
            cfg.appendChild(enumSel);
            return { value: () => enumSel.value.trim() || null };
        };

        const buildDynamic = () => {
            cfg.innerHTML = '';
            const sel = el('select', { multiple: true });
            Object.keys(classesRes || {}).forEach(c => sel.appendChild(el('option', { value: c, textContent: c })));
            cfg.appendChild(sel);
            const chooser = new Choices(sel, { removeItemButton: true, shouldSort: true, itemSelectText: '' });
            if (Array.isArray(prefill.classes)) prefill.classes.forEach(c => chooser.setChoiceByValue(c));
            return { value: () => chooser.getValue(true) };
        };

        const buildFree = () => {
            cfg.innerHTML = '';
            const kind = el('select', {});
            [['text', 'text'], ['number', 'number']].forEach(([v, t]) => kind.appendChild(el('option', { value: v, textContent: t })));
            if (prefill.text_type) kind.value = prefill.text_type;
            cfg.appendChild(kind);
            return { value: () => kind.value };
        };

        let cfgGetter = null;
        const refreshCfg = () => {
            if (type.value === 'fixed') cfgGetter = buildFixed();
            else if (type.value === 'dynamic') cfgGetter = buildDynamic();
            else cfgGetter = buildFree();

            const k = (name.value || '').trim();
            if (!desc.value && k && generalQualifiers[k]) desc.value = generalQualifiers[k];
        };

        type.addEventListener('change', refreshCfg);
        name.addEventListener('change', () => {
            const k = name.value.trim();
            if (!desc.value && k && generalQualifiers[k]) desc.value = generalQualifiers[k];
        });
        refreshCfg();

        row.appendChild(name);
        row.appendChild(type);
        row.appendChild(cfg);
        row.appendChild(optWrap);
        row.appendChild(desc);
        row.appendChild(del);

        list.appendChild(row);
        return { row };
    };

    $('#pr-add-field').onclick = () => addFieldRow();
    $('#pr-add-defaults').onclick = () => {
        for (const [k, v] of Object.entries(generalQualifiers)) addFieldRow({ name: k, kind: 'fixed', description: v });
        status.textContent = `Added ${Object.keys(generalQualifiers).length} common qualifiers.`;
    };
    $('#pr-reset-fields').onclick = () => { list.innerHTML = ''; status.textContent = 'All relation fields cleared.'; };

    // NEW: a local "Create Enum" button (if you add one in the relation page header)
    // It will also work if you have a global toolbar button wired by the router.
    const localCreateEnumBtn = $('#pr-create-enum');
    if (localCreateEnumBtn && !localCreateEnumBtn.dataset.bound) {
        localCreateEnumBtn.dataset.bound = '1';
        localCreateEnumBtn.onclick = () => { location.hash = '#/propose-enum'; };
    }

    $('#btn-propose-rel-back').onclick = () => { location.hash = '#/'; };

    $('#btn-propose-rel-save').onclick = async () => {
        try {
            const relName = ($('#pr-name').value || '').trim();
            if (!/^[A-Z][A-Za-z0-9_]*$/.test(relName)) { status.textContent = 'Invalid relation name (CamelCase).'; return; }
            const subject_classes = subjChoices.getValue(true);
            const object_classes = objChoices.getValue(true);
            if (!subject_classes.length || !object_classes.length) { status.textContent = 'Pick at least one subject and one object class.'; return; }
            const predRaw = (predsInp.value || '').trim();
            const predicate_choices = predRaw ? predRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

            const rows = Array.from(list.querySelectorAll('.attr-row'));
            const fields = [];
            for (const r of rows) {
                const [nameEl, typeEl, cfgEl, optEl, descEl] = r.children;
                const fname = (nameEl.value || '').trim();
                if (!fname) continue;
                if (!/^[a-z_][a-z0-9_]*$/.test(fname)) { status.textContent = `Invalid field name "${fname}"`; return; }
                const kind = typeEl.value;
                const optional = !!optEl.querySelector('input[type="checkbox"]').checked;
                const description = (descEl.value || '').trim();
                const field = { name: fname, kind, optional, description };
                if (kind === 'fixed') {
                    const sel = cfgEl.querySelector('select[data-role="enum-select"]');
                    const chosen = (sel?.value || '').trim();
                    if (!chosen) { status.textContent = `Field "${fname}": choose an enum.`; return; }
                    field.enum_name = chosen;
                } else if (kind === 'dynamic') {
                    const sel = cfgEl.querySelector('select');
                    const classes = sel ? Array.from(sel.selectedOptions).map(o => o.value) : [];
                    if (!classes.length) { status.textContent = `Field "${fname}" needs allowed classes.`; return; }
                    field.classes = classes;
                } else if (kind === 'free_text') {
                    const tsel = cfgEl.querySelector('select');
                    field.text_type = tsel ? tsel.value : 'text';
                }
                fields.push(field);
            }

            const payload = { name: relName, description: ($('#pr-desc').value || '').trim(), subject_classes, object_classes, predicate_choices, fields };
            status.textContent = 'Saving…';
            const res = await API.proposeRelation(payload);
            status.textContent = `Saved! Appended to ${res.proposed_file}. Enums created: ${(res.enums_created || []).join(', ') || 'none'}.`;
            $('#pr-name').value = ''; $('#pr-desc').value = ''; predsInp.value = ''; list.innerHTML = '';
        } catch (e) {
            status.textContent = e.message || String(e);
        }
    };

    // Make refresh available to other modules
    window.refreshEnumOptions = refreshEnumOptions;
}
