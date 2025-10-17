import { API_BASE } from '../core/config.js';

async function jfetch(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
}

export const API = {
    getClasses: () => jfetch(`${API_BASE}/api/classes`),
    getRelations: () => jfetch(`${API_BASE}/api/relations`),
    getNextText: (cursor = null) => {
        const url = new URL(`${API_BASE}/api/texts/next`);
        if (cursor !== null) url.searchParams.set('cursor', cursor);
        return jfetch(url);
    },
    getPrevText: (cursor) => {
        const url = new URL(`${API_BASE}/api/texts/prev`);
        url.searchParams.set('cursor', cursor);
        return jfetch(url);
    },
    annotationsExist: (text_id) =>
        jfetch(`${API_BASE}/api/annotations/${encodeURIComponent(text_id)}/exists`),
    getAnnotation: (text_id) =>
        fetch(`${API_BASE}/api/annotations/${encodeURIComponent(text_id)}`)
            .then(r => (r.status === 404 ? null : r.json())),
    saveAnnotations: (payload, overwrite = false) => {
        const url = new URL(`${API_BASE}/api/annotations`);
        if (overwrite) url.searchParams.set('overwrite', 'true');
        return jfetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    semanticStatus: (kind = 'class') =>
        jfetch(`${API_BASE}/api/semantic/status?kind=${encodeURIComponent(kind)}`),
    semanticSuggest: (payload) =>
        jfetch(`${API_BASE}/api/semantic/suggest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }),
    proposeClass: (payload) =>
        jfetch(`${API_BASE}/api/proposed-classes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }),
    getEnums: () => jfetch(`${API_BASE}/api/enums`),
    createEnum: (payload) =>
        jfetch(`${API_BASE}/api/enums`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }),
    getFieldDescriptions: () => jfetch(`${API_BASE}/api/field-descriptions`),
    proposeRelation: (payload) =>
        jfetch(`${API_BASE}/api/proposed-relations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }),
};
