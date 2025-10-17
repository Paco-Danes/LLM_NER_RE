import { $, el } from '../utils/dom.js';
import { API } from '../api/index.js';

let loaded = false;

export async function showProposeEnumPage() {
    let overlay = $('#propose-enum-overlay');
    if (!overlay) {
        overlay = el('div', { id: 'propose-enum-overlay', className: 'page-overlay', style: 'display:none' });
        $('.main')?.appendChild(overlay);
    }
    if (!loaded) {
        const html = await (await fetch('/partials/propose-enum.html')).text();
        overlay.innerHTML = html;
        loaded = true;
        init();
    }
    overlay.style.display = 'block';
    $('#propose-enum-status').textContent = 'Create a new enum or inspect existing ones.';
    if (location.hash !== '#/propose-enum') location.hash = '#/propose-enum';
}

export function hideProposeEnumPage() {
    const overlay = $('#propose-enum-overlay');
    if (overlay) overlay.style.display = 'none';
    if (location.hash === '#/propose-enum') history.replaceState(null, '', ' ');
}

function init() {
    const status = $('#propose-enum-status');
    const listWrap = $('#pe-enum-list');

    const renderEnums = async () => {
        try {
            const enums = await API.getEnums();
            listWrap.innerHTML = '';
            const names = Object.keys(enums).sort((a, b) => a.localeCompare(b));
            if (!names.length) {
                listWrap.appendChild(el('div', { className: 'empty' }, ['No enums found.']));
                return;
            }
            const chunk = (arr) => {
                const size = (arr.length <= 20) ? 5 : 15;
                const out = [];
                for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
                return out;
            };
            for (const name of names) {
                const det = document.createElement('details');
                const sum = document.createElement('summary');
                sum.textContent = name;
                det.appendChild(sum);
                const values = enums[name] || [];
                const colsWrap = document.createElement('div'); colsWrap.className = 'enum-columns';
                const cols = chunk(values);
                for (const col of cols) {
                    const ul = document.createElement('ul'); ul.className = 'enum-col';
                    for (const v of col) {
                        const li = document.createElement('li'); li.textContent = v; ul.appendChild(li);
                    }
                    colsWrap.appendChild(ul);
                }
                det.appendChild(colsWrap);
                listWrap.appendChild(det);
            }
        } catch (e) {
            listWrap.innerHTML = '';
            listWrap.appendChild(el('div', { className: 'empty' }, ['Failed to load enums.']));
        }
    };

    const coerceName = (raw) => {
        let s = (raw || '').trim();
        s = s.replace(/[^A-Za-z0-9_]+/g, '_').toUpperCase();
        if (!s.endsWith('_ENUM')) s = s + '_ENUM';
        return s;
    };

    $('#btn-propose-enum-back').onclick = () => {
        // route to the relation builder; router will hide/show the right overlays
        location.hash = '#/propose-relation';
        // let the relation page refresh enum selects
        window.dispatchEvent(new Event('refresh-enums-elsewhere'));
    };

    $('#btn-propose-enum-save').onclick = async () => {
        try {
            const rawName = $('#pe-name').value;
            const name = coerceName(rawName);
            const rawVals = ($('#pe-values').value || '').trim();
            const values = rawVals.split(',').map(s => s.trim()).filter(Boolean);
            if (!name.match(/^[A-Z_][A-Z0-9_]*$/)) { status.textContent = 'Invalid enum name.'; return; }
            if (!values.length) { status.textContent = 'Please enter at least one value.'; return; }
            status.textContent = 'Saving…';
            await API.createEnum({ name, values });
            status.textContent = `Saved enum ${name}.`;
            await renderEnums();
            $('#pe-name').value = name;
            window.dispatchEvent(new Event('refresh-enums-elsewhere'));
        } catch (e) {
            status.textContent = e.message || String(e);
        }
    };

    renderEnums();
}
