export const API_BASE = 'http://localhost:8000';

export function ensureChoices() {
    if (!('Choices' in window)) {
        throw new Error('Choices.js not loaded');
    }
    return window.Choices;
}
