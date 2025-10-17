import { state } from './state.js';

export function entityById(id) {
    return state.annotations.find(a => a.id === id) || null;
}

export function spanToTokenRange(span) {
    const { start, end } = span; // end exclusive
    let i0 = null, i1 = null;
    for (let i = 0; i < state.tokens.length; i++) {
        const t = state.tokens[i];
        if (t.isSpace) continue;
        if (i0 === null && t.end > start) i0 = i;
        if (t.start < end) i1 = i;
        if (t.start >= end) break;
    }
    if (i0 === null || i1 === null) return null;
    return [i0, i1];
}

export function buildAnnotationPayload() {
    return {
        text_id: state.current.id,
        text: state.current.text,
        entities: state.annotations.map(a => ({
            id: a.id,
            class: a.class,
            label: a.label,
            span: { start: a.span.start, end: a.span.end },
            attributes: a.attrs
        })),
        relations: state.relations.map(r => ({
            id: r.id,
            predicate: r.predicate || '',
            subject: r.subject,
            object: r.object,
            attributes: r.attrs || {}
        })),
    };
}

export function surfaceFormFromSelection() {
    const { startIdx, endIdx } = state.selection;
    if (startIdx === null || endIdx === null) return '';
    const parts = [];
    for (let i = startIdx; i <= endIdx; i++) {
        const t = state.tokens[i];
        if (!t || t.isSpace) continue;
        parts.push(t.text);
        const after = state.tokens[i + 1];
        if (after && after.isSpace) parts.push(after.text);
    }
    return parts.join('').trim();
}
