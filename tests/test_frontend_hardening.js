// Run with JavaScriptCore from the repository root; no browser or network needed.
const source = readFile('static/js/nova_v3.js');
new Function(source);
function assert(condition, message) {
    if (!condition) throw new Error(message);
}
class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.append(child); return child; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    set innerHTML(value) {
        assert(!value.includes('onerror'), 'Stored text was parsed as HTML');
        this.children = [];
    }
}
const count = new Element('span');
const document = {
    createElement: tag => new Element(tag),
    createTextNode: text => ({tag: '#text', textContent: text}),
    getElementById: () => count,
    querySelector: () => ({content: 'csrf-test'})
};
class Headers {
    constructor(initial = {}) { this.values = {...initial}; }
    set(key, value) { this.values[key] = value; }
}
let requestOptions;
const fetch = (url, options) => { requestOptions = options; return Promise.resolve({}); };
eval(source.slice(0, source.indexOf('// ========================================')));
novaFetch('/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
assert(requestOptions.headers.values['X-CSRF-Token'] === 'csrf-test', 'Missing CSRF header');
assert(requestOptions.headers.values['Content-Type'] === 'application/json', 'JSON header changed');
novaFetch('/api/projects');
assert(!requestOptions.headers.values['X-CSRF-Token'], 'CSRF added to GET');
const hostile = '<img src=x onerror=alert(1)>';
const popup = safePopupContent(hostile, hostile);
assert(popup.children[0].textContent === hostile, 'Popup title changed');
assert(popup.children[2].tag === '#text', 'Popup detail is not plain text');

const list = new Element('div');
const recent = new Element('div');
let opened = false;
const start = source.indexOf('async function loadProjects()');
const end = source.indexOf('// CREATE PROJECT', start);
const run = new Function('projectsList', 'recentProjects', 'document', 'novaFetch', 'openProject',
    source.slice(start, end) + '\nreturn loadProjects();');
run(list, recent, document,
    async () => ({ok: true, json: async () => ({projects: [{id: 1, name: hostile, description: hostile}]})}),
    () => { opened = true; }
).then(() => {
    assert(list.children[0].children[0].children[0].textContent === '📁 ' + hostile, 'Project name not preserved as text');
    assert(list.children[0].children[0].children[1].textContent === hostile, 'Project description not preserved as text');
    assert(recent.children[0].children[1].children[0].textContent === hostile, 'Recent project unsafe');
    list.children[0].children[1].listeners.click();
    assert(opened, 'Open Project stopped working');
    print('PASS: JavaScript syntax, CSRF headers, literal hostile project/popup text, and Open Project handler.');
}).catch(error => { print(error); quit(1); });
