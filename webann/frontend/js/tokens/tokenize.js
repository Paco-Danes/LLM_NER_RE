export function tokenizeWithOffsets(text) {
    const tokens = [];
    let i = 0;
    const re = /(\s+|\w+|[^\w\s])/gu;
    let m;
    while ((m = re.exec(text)) !== null) {
        const tok = m[0];
        const isSpace = /\s/u.test(tok);
        tokens.push({ text: tok, start: i, end: i + tok.length, isSpace });
        i += tok.length;
    }
    return tokens;
}
