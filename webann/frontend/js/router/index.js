import { showProposeClassPage, hideProposeClassPage } from '../pages/proposeClass.js';
import { showProposeRelationPage, hideProposeRelationPage } from '../pages/proposeRelation.js';
import { showProposeEnumPage, hideProposeEnumPage } from '../pages/proposeEnum.js';

function bindIfPresent(selector, handler) {
    const el = document.querySelector(selector);
    if (el && !el.dataset.bound) {
        el.addEventListener('click', handler);
        el.dataset.bound = '1';
    }
}

export function initRouter() {
    // Deep links on first load
    if (location.hash === '#/propose-class') showProposeClassPage();
    if (location.hash === '#/propose-relation') showProposeRelationPage();
    if (location.hash === '#/propose-enum') showProposeEnumPage();

    // Hash routing
    window.addEventListener('hashchange', () => {
        const h = location.hash;
        if (h === '#/propose-class') showProposeClassPage(); else hideProposeClassPage();
        if (h === '#/propose-relation') showProposeRelationPage(); else hideProposeRelationPage();
        if (h === '#/propose-enum') showProposeEnumPage(); else hideProposeEnumPage();
    });

    // After partials load, bind toolbar/side buttons
    document.addEventListener('partials:loaded', () => {
        bindIfPresent('#btn-propose', () => location.hash = '#/propose-class');
        bindIfPresent('#btn-propose-rel', () => location.hash = '#/propose-relation');
        bindIfPresent('#btn-propose-enum', () => location.hash = '#/propose-enum');
    });

    // Event delegation fallback: if buttons are injected later or re-rendered
    document.addEventListener('click', (e) => {
        const t = e.target.closest('#btn-propose, #btn-propose-rel, #btn-propose-enum, [data-route]');
        if (!t) return;
        const route = t.getAttribute('data-route');
        if (t.id === 'btn-propose') location.hash = '#/propose-class';
        else if (t.id === 'btn-propose-rel') location.hash = '#/propose-relation';
        else if (t.id === 'btn-propose-enum') location.hash = '#/propose-enum';
        else if (route) location.hash = route;
    });

    // When enum list changes elsewhere, refresh relation page enum selects
    window.addEventListener('refresh-enums-elsewhere', () => {
        if (typeof window.refreshEnumOptions === 'function') window.refreshEnumOptions();
    });
}
