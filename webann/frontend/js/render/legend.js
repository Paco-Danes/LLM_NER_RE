import { $, el } from '../utils/dom.js';
import { state } from '../core/state.js';
import { classColor } from '../utils/colors.js';
import { openEntityModal } from '../modals/entity.js';

export function renderLegend() {
    const legend = $('#legend');
    const empty = $('#legend-empty');
    if (!legend) return;
    legend.innerHTML = '';

    if (!state.annotations.length) {
        if (empty) empty.style.display = 'block';
        const delAll = $('#btn-delete-all');
        if (delAll) delAll.disabled = true;
        return;
    }
    if (empty) empty.style.display = 'none';

    const delAll = $('#btn-delete-all');
    if (delAll) delAll.disabled = false;

    const byClass = {};
    for (const a of state.annotations) {
        byClass[a.class] ??= [];
        byClass[a.class].push(a);
    }

    for (const [klass, annos] of Object.entries(byClass)) {
        const colors = classColor(klass);
        const header = el('div', { className: 'header', style: `background:${colors.chip}; border-bottom:1px solid ${colors.border}` }, [klass]);

        const itemsDiv = el('div', { className: 'items' });
        for (const a of annos) {
            const chip = el('span', {
                className: 'chip',
                style: `background:${colors.chip}; border-color:${colors.border}`,
                dataset: { annoId: a.id },
                draggable: true
            }, [a.label || `${klass}`]);

            chip.addEventListener('click', () => openEntityModal('edit', a.id));
            chip.addEventListener('dragstart', (ev) => {
                ev.dataTransfer.setData('text/plain', a.id);
                ev.dataTransfer.effectAllowed = 'copy';
            });

            itemsDiv.appendChild(chip);
        }

        const card = el('div', { className: 'class-card' }, [header, itemsDiv]);
        legend.appendChild(card);
    }
}
