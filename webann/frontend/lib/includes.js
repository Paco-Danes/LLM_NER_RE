export async function includePartials(root = document) {
    const nodes = Array.from(root.querySelectorAll('[data-include]'));
    await Promise.all(nodes.map(async el => {
        const url = el.getAttribute('data-include');
        const res = await fetch(url, { credentials: 'same-origin' });
        if (!res.ok) throw new Error(`Failed to load ${url}: ${res.status}`);
        el.innerHTML = await res.text();
        const nested = el.querySelector('[data-include]');
        if (nested) await includePartials(el);
    }));
    // NEW: let the app know partials are ready so it can bind handlers
    document.dispatchEvent(new CustomEvent('partials:loaded'));
}
