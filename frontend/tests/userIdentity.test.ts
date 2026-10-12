import assert from 'node:assert/strict';
import test from 'node:test';
import { authenticatedDisplayName } from '../src/userIdentity.ts';

test('uses the registered account name after trimming whitespace', () => {
  assert.equal(authenticatedDisplayName('  Asha Rao  '), 'Asha Rao');
});

test('uses Farmer when a legacy account has no display name', () => {
  assert.equal(authenticatedDisplayName(''), 'Farmer');
  assert.equal(authenticatedDisplayName(null), 'Farmer');
  assert.equal(authenticatedDisplayName(undefined), 'Farmer');
});
