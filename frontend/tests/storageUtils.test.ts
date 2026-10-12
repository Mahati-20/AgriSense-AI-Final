import assert from 'node:assert/strict';
import test from 'node:test';
import { filterAndSortStorage, storageListState } from '../src/storageUtils.ts';

const facilities = [
  { id: 1, name: 'East cold store', location: 'Bengaluru East', distance: 12, capacity: 100, available_capacity: 80, storage_type: 'Cold Storage', price_per_day: 22, rating: 4.8 },
  { id: 2, name: 'Nandi warehouse', location: 'Devanahalli', distance: 18, capacity: 200, available_capacity: 120, storage_type: 'Warehouse', price_per_day: 16, rating: 4.5 },
  { id: 3, name: 'Whitefield dry store', location: 'Whitefield', distance: 10, capacity: 90, available_capacity: 70, storage_type: 'Dry Storage', price_per_day: 14, rating: 4.3 },
  { id: 4, name: 'South warehouse', location: 'Bengaluru South', distance: 6, capacity: 140, available_capacity: 60, storage_type: 'Warehouse', price_per_day: 11, rating: 4.2 },
];

test('location and storage type filters combine and remain case insensitive', () => {
  const results = filterAndSortStorage(facilities, ' BENGALURU ', 'Warehouse', 'distance');
  assert.deepEqual(results.map((item) => item.id), [4]);
});

test('sorting supports distance, price, and rating without mutating input', () => {
  assert.deepEqual(filterAndSortStorage(facilities, '', 'All', 'distance').map((item) => item.id), [4, 3, 1, 2]);
  assert.deepEqual(filterAndSortStorage(facilities, '', 'All', 'price').map((item) => item.id), [4, 3, 2, 1]);
  assert.deepEqual(filterAndSortStorage(facilities, '', 'All', 'rating').map((item) => item.id), [1, 2, 3, 4]);
  assert.deepEqual(facilities.map((item) => item.id), [1, 2, 3, 4]);
});

test('location with no matches returns a true empty list', () => {
  assert.deepEqual(filterAndSortStorage(facilities, 'Mysuru', 'All', 'distance'), []);
});

test('loading and API errors take precedence over the empty-results view', () => {
  assert.equal(storageListState(true, '', 0), 'loading');
  assert.equal(storageListState(false, 'Backend unavailable', 0), 'error');
  assert.equal(storageListState(false, '', 0), 'empty');
  assert.equal(storageListState(false, '', 2), 'results');
});
