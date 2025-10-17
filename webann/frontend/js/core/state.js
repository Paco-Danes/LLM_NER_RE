export const state = {
    classes: {},
    texts: { cursor: 0, total: 0 },
    current: null,                 // { id, text }
    tokens: [],
    selection: { startIdx: null, endIdx: null },
    annotations: [],               // [{ id, class, label, attrs, span, tokenRange }]
    saved: { exists: false, wasEmpty: false },
    relations: [],                 // [{ id, predicate|null, subject, object|null, attrs, attrOrder? }]
    relationsMeta: {},             // name -> meta
};

export const ui = {
    mode: 'create',
    editId: null,
    dragging: false,
    relEditingId: null,
    dirty: false,
};
