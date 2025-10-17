import { $ } from '../utils/dom.js';

export function openOverwriteModal(onConfirm, onCancel) {
    const bd = $('#overwrite-bd');
    if (!bd) return;
    bd.style.display = 'flex';
    const ok = $('#btn-overwrite-confirm');
    const cancel = $('#btn-overwrite-cancel');
    const cleanup = () => { if (ok) ok.onclick = null; if (cancel) cancel.onclick = null; bd.style.display = 'none'; };
    if (ok) ok.onclick = () => { cleanup(); onConfirm && onConfirm(); };
    if (cancel) cancel.onclick = () => { cleanup(); onCancel && onCancel(); };
}

export function openDeleteAllModal(onConfirm, onCancel) {
    const bd = $('#delall-bd');
    if (!bd) return;
    bd.style.display = 'flex';
    const ok = $('#btn-delall-confirm');
    const cancel = $('#btn-delall-cancel');
    const cleanup = () => { if (ok) ok.onclick = null; if (cancel) cancel.onclick = null; bd.style.display = 'none'; };
    if (ok) ok.onclick = () => { cleanup(); onConfirm && onConfirm(); };
    if (cancel) cancel.onclick = () => { cleanup(); onCancel && onCancel(); };
}
