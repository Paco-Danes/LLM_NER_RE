import { $, el } from '../utils/dom.js';
import { API } from '../api/index.js';
import { classColor } from '../utils/colors.js';

export function wireSemanticButtons() {
    const btn = $('#btn-sem-find');
    if (!btn) return;

    API.semanticStatus().then(s => {
        btn.disabled = !(s.ready && s.has_embedder && s.size > 0);
        btn.title = btn.disabled ? 'Semantic index not ready' : 'Send search + label to semantic engine';
    });

    btn.addEventListener('click', async () => {
        try {
            btn.classList.add('loading');
            const inp = document.querySelector('#modal-bd .choices__input--cloned');
            const query = (inp && inp.value.trim()) || '';
            const label = ($('#inp-label')?.value || '').trim();
            const res = await API.semanticSuggest({ query, label, top_k: 10, threshold: 0.2 });
            renderSemanticSuggestions(res.items);
        } catch (e) {
            alert('Semantic search failed: ' + e.message);
        } finally {
            btn.classList.remove('loading');
        }
    });
}

export function renderSemanticSuggestions(items) {
    const section = $('#sem-suggest-section');
    const box = $('#sem-suggest');
    if (!section || !box) return;
    box.innerHTML = '';

    if (!items || !items.length) {
        section.style.display = 'block';
        box.appendChild(el('span', { className: 'empty' }, ['No semantic suggestions.']));
        return;
    }

    for (const it of items) {
        const colors = classColor(it.class_name);
        const chip = el('span', {
            className: 'chip',
            style: `background:${colors.chip}; border-color:${colors.border}`,
            title: it.description || ''
        }, [
            it.class_name, ' ', el('small', {}, [`${Math.round(it.score * 100)}%`])
        ]);

        chip.addEventListener('click', () => {
            const sel = $('#sel-class');
            if (!sel) return;
            for (const o of sel.options) { o.selected = (o.value === it.class_name); }
            sel.dispatchEvent(new Event('change'));
        });

        box.appendChild(chip);
    }
    section.style.display = 'block';
}
