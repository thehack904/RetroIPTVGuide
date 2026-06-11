"""Focused tests for user-prefs channel number overlay behavior."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module


def _simulate_user_prefs_channel_numbers(channels, body_classes=None, add_channel=None):
    js_path = Path(app_module.app.static_folder) / "js" / "user-prefs.js"
    payload = json.dumps({
        "channels": channels,
        "body_classes": body_classes or [],
        "add_channel": add_channel,
        "script_path": str(js_path),
    })
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(process.argv[1]);
const source = fs.readFileSync(input.script_path, 'utf8');

function makeClassList(initial = []) {
  const s = new Set(initial);
  return {
    add: (...items) => items.forEach(i => s.add(i)),
    remove: (...items) => items.forEach(i => s.delete(i)),
    toggle: (item, force) => {
      if (force === true) { s.add(item); return true; }
      if (force === false) { s.delete(item); return false; }
      if (s.has(item)) { s.delete(item); return false; }
      s.add(item); return true;
    },
    contains: (item) => s.has(item)
  };
}

function makeUserNumNode(text) {
  return {
    className: 'user-channel-number',
    textContent: text,
    remove: function () {
      if (!this._parent) return;
      const i = this._parent._children.indexOf(this);
      if (i >= 0) this._parent._children.splice(i, 1);
      this._parent = null;
    }
  };
}

function makeChannel(cid, hasBuiltIn) {
  const el = {
    dataset: { cid },
    _children: [],
    firstChild: null,
    addEventListener: () => {},
    closest: () => null,
    querySelector: (sel) => {
      if (sel === '.channel-number') return hasBuiltIn ? { className: 'channel-number' } : null;
      if (sel === '.user-channel-number') return el._children.find(n => n.className === 'user-channel-number') || null;
      return null;
    },
    insertBefore: (node) => {
      node._parent = el;
      el._children.unshift(node);
      el.firstChild = el._children[0] || null;
    }
  };
  return el;
}

const chanEls = input.channels.map(ch => makeChannel(ch.cid, !!ch.built_in));
const rows = input.channels.map(ch => ({ dataset: { cid: ch.cid }, classList: makeClassList() }));
const guideOuter = {};
let domReadyCb = null;
let mutationCb = null;

const document = {
  readyState: 'loading',
  body: { classList: makeClassList(input.body_classes || []) },
  querySelectorAll: (sel) => {
    if (sel === '.guide-row[data-cid]') return rows;
    if (sel === '.guide-row[data-cid] .chan-name') return chanEls;
    if (sel === '.chan-name') return chanEls;
    if (sel === '.chan-name .user-channel-number') {
      return chanEls.flatMap(ch => ch._children.filter(n => n.className === 'user-channel-number'));
    }
    return [];
  },
  getElementById: (id) => (id === 'guideOuter' ? guideOuter : null),
  addEventListener: (event, cb) => {
    if (event === 'DOMContentLoaded') domReadyCb = cb;
  },
  createElement: (tag) => {
    if (tag === 'span') return makeUserNumNode('');
    return { className: '', textContent: '', remove: () => {} };
  }
};

const windowObj = {
  __initialUserPrefs: { channel_numbers_enabled: true },
  addEventListener: () => {},
  console,
};

function MutationObserver(cb) {
  this.observe = () => { mutationCb = cb; };
}

const context = {
  document,
  window: windowObj,
  MutationObserver,
  fetch: async () => ({ ok: true, json: async () => ({ prefs: { channel_numbers_enabled: true } }) }),
  alert: () => {},
  CSS: { escape: (s) => s },
  setTimeout: (fn) => { fn(); return 1; },
  clearTimeout: () => {},
  console,
};

vm.runInNewContext(source, context, { filename: 'user-prefs.js' });
if (domReadyCb) domReadyCb();

function labels() {
  return chanEls.map(ch => {
    const n = ch.querySelector('.user-channel-number');
    return n ? n.textContent : '';
  });
}

const out = { initial: labels() };

if (input.add_channel) {
  chanEls.push(makeChannel(input.add_channel.cid, !!input.add_channel.built_in));
  rows.push({ dataset: { cid: input.add_channel.cid }, classList: makeClassList() });
  if (mutationCb) mutationCb([{ type: 'childList', addedNodes: [1], removedNodes: [] }]);
  out.afterMutation = labels();
}

process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "-e", node_script, payload],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_user_channel_numbers_follow_current_row_order():
    result = _simulate_user_prefs_channel_numbers(
        channels=[
            {"cid": "virtual.news"},
            {"cid": "real.1"},
            {"cid": "real.2"},
        ],
        add_channel={"cid": "virtual.weather"},
    )
    assert result["initial"] == ["CH 1", "CH 2", "CH 3"]
    assert result["afterMutation"] == ["CH 1", "CH 2", "CH 3", "CH 4"]


def test_user_channel_numbers_not_injected_for_builtin_number_theme():
    result = _simulate_user_prefs_channel_numbers(
        channels=[
            {"cid": "virtual.news"},
            {"cid": "real.1"},
        ],
        body_classes=["tvguide1990"],
    )
    assert result["initial"] == ["", ""]
