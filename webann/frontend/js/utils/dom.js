export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    const { dataset, ...rest } = props;
    Object.assign(node, rest);
    if (dataset) Object.entries(dataset).forEach(([k, v]) => node.dataset[k] = v);
    for (const c of (children || [])) node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    return node;
}
