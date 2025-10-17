import { $$ } from '../utils/dom.js';
import { state } from '../core/state.js';
import { classColor } from '../utils/colors.js';

export function applyAnnotationHighlights() {
    $$('.token').forEach(s => {
        s.style.background = 'transparent';
        s.dataset.annotated = 'false';
        s.removeAttribute('data-anno-label');
        s.dataset.selected = 'false';
    });
    for (const anno of state.annotations) {
        const colors = classColor(anno.class);
        const [i0, i1] = anno.tokenRange;
        for (let i = i0; i <= i1; i++) {
            const node = document.querySelector(`.token[data-idx="${i}"]`);
            if (!node) continue;
            node.style.background = colors.bg;
            node.dataset.annotated = 'true';
            node.setAttribute('data-anno-label', `${anno.class}`);
        }
    }
}
