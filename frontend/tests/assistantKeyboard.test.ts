import assert from 'node:assert/strict';
import test from 'node:test';
import { shouldSubmitAssistantOnEnter } from '../src/assistantKeyboard.ts';

test('Enter submits a chat message', () => {
  assert.equal(shouldSubmitAssistantOnEnter('Enter', false, false), true);
});

test('Shift+Enter preserves textarea newline behavior', () => {
  assert.equal(shouldSubmitAssistantOnEnter('Enter', true, false), false);
});

test('Enter during IME composition does not submit', () => {
  assert.equal(shouldSubmitAssistantOnEnter('Enter', false, true), false);
});

test('other keys do not submit', () => {
  assert.equal(shouldSubmitAssistantOnEnter('Escape', false, false), false);
});
