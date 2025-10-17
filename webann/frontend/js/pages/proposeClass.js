import { $, el } from '../utils/dom.js';
import { API } from '../api/index.js';

let loaded = false;

export async function showProposeClassPage() {
    let overlay = $('#propose-overlay');
    if (!overlay) {
        overlay = el('div', { id: 'propose-overlay', className: 'page-overlay', style: 'display:none' });
        $('.main')?.appendChild(overlay);
    }
    if (!loaded) {
        const html = await (await fetch('/partials/propose-class.html')).text();
        overlay.innerHTML = html;
        loaded = true;
        init();
    }
    overlay.style.display = 'block';
    $('#propose-status').textContent = 'Fill out the class and click Save.';
    if (location.hash !== '#/propose-class') location.hash = '#/propose-class';
}

export function hideProposeClassPage() {
    const overlay = $('#propose-overlay');
    if (overlay) overlay.style.display = 'none';
    if (location.hash === '#/propose-class') history.replaceState(null, '', ' ');
}

function init() {
    const list = $('#pc-attr-list');

    const addAttrRow = (prefill = {}) => {
        const row = el('div', { className: 'attr-row' });
        const name = el('input', { type: 'text', placeholder: 'snake_case', value: prefill.name || '' });
        name.pattern = '^[a-z_][a-z0-9_]*$';
        const type = el('select', {});
        ['str', 'int', 'float', 'bool', 'literal', 'list[str]', 'list[int]', 'list[float]', 'list[bool]']
            .forEach(t => type.appendChild(el('option', { value: t, textContent: t })));
        type.value = prefill.type || 'str';
        const opt = el('input', { type: 'checkbox', title: 'Optional' });
        opt.checked = !!prefill.optional;
        const lit = el('input', { type: 'text', placeholder: 'e.g., CS, PCW, GW', value: (prefill.literal_values || []).join(', ') });
        const desc = el('input', { type: 'text', placeholder: 'Field description', value: prefill.description || '' });
        const del = el('button', { type: 'button', className: 'ghost', textContent: '✕' });
        del.onclick = () => row.remove();

        const litWrap = el('div', { className: 'lit-wrap' }, [lit]);
        const toggleLit = () => {
            const isLit = type.value === 'literal';
            litWrap.style.visibility = isLit ? 'visible' : 'hidden';
            litWrap.style.pointerEvents = isLit ? 'auto' : 'none';
            if (!isLit) lit.value = '';
        };
        type.addEventListener('change', toggleLit);
        toggleLit();

        row.appendChild(name);
        row.appendChild(type);
        row.appendChild(opt);
        row.appendChild(litWrap);
        row.appendChild(desc);
        row.appendChild(del);
        list.appendChild(row);
    };

    if (!list.childElementCount) addAttrRow();
    $('#pc-attr-add').onclick = () => addAttrRow();
    $('#btn-propose-back').onclick = hideProposeClassPage;

    $('#btn-propose-save').onclick = async () => {
        const status = $('#propose-status');
        try {
            const className = ($('#pc-name').value || '').trim();
            const doc = ($('#pc-desc').value || '').trim();
            if (!/^[A-Z][A-Za-z0-9_]*$/.test(className)) {
                status.textContent = 'Invalid class name. Use CamelCase.';
                return;
            }
            const rows = Array.from(list.querySelectorAll('.attr-row'));
            const seen = new Set();
            const attrs = [];
            for (const r of rows) {
                const [name, type, opt, litWrap, desc] = r.children;
                const nm = name.value.trim();
                if (!nm) continue;
                if (!/^[a-z_][a-z0-9_]*$/.test(nm)) { status.textContent = `Invalid field "${nm}"`; return; }
                if (seen.has(nm)) { status.textContent = `Duplicate field "${nm}"`; return; }
                seen.add(nm);
                const t = type.value;
                const optional = opt.checked;
                const description = desc.value.trim();
                const spec = { name: nm, type: t, optional, description };
                if (t === 'literal') {
                    const raw = litWrap.querySelector('input').value.trim();
                    const vals = raw ? raw.split(',').map(s => s.trim()).filter(Boolean) : [];
                    if (!vals.length) { status.textContent = `Literal field "${nm}" needs values`; return; }
                    spec.literal_values = vals;
                }
                attrs.push(spec);
            }
            const payload = { name: className, description: doc, attributes: attrs };
            status.textContent = 'Saving…';
            await API.proposeClass(payload);
            status.textContent = `Saved! Appended class ${className} to proposed_classes.py`;
            $('#pc-name').value = '';
            $('#pc-desc').value = '';
            list.innerHTML = '';
            addAttrRow();
        } catch (e) {
            status.textContent = e.message || String(e);
        }
    };
}
