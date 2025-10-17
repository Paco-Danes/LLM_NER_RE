const PALETTE = [
    '#ff0000', '#ff8800', '#fffa00', '#cbff00', '#72ff00',
    '#00ffb3', '#00c9ff', '#0088ff', '#0016ff', '#8d00ff',
    '#b600ff', '#ff00f7', '#ff0075', '#ff004c', '#ffb800',
    '#00f1ff',
];

const CLASS_COLORS = {};
let nextColorIdx = 0;

export function classColor(klass) {
    if (!(klass in CLASS_COLORS)) {
        CLASS_COLORS[klass] = PALETTE[nextColorIdx % PALETTE.length];
        nextColorIdx++;
    }
    const base = CLASS_COLORS[klass];
    return {
        bg: base + '66',
        chip: base + '44',
        border: base + '99',
    };
}
