import assert from 'node:assert/strict';
import test from 'node:test';
import { convertAgriculturalUnit, escapeCsvCell, isValidDateKey, monthCalendarDays } from '../src/farmToolUtils.ts';

test('mass conversions use metric units and support decimals', () => {
  assert.equal(convertAgriculturalUnit(1250, 'kg', 'tonnes'), 1.25);
  assert.equal(convertAgriculturalUnit(1.25, 'tonnes', 'kg'), 1250);
});

test('area, volume and price conversions use the stated constants', () => {
  assert.equal(convertAgriculturalUnit(1, 'acres', 'hectares'), 0.40468564224);
  assert.equal(convertAgriculturalUnit(1, 'hectares', 'acres'), 2.47105381467);
  assert.equal(convertAgriculturalUnit(10000, 'm²', 'hectares'), 1);
  assert.equal(convertAgriculturalUnit(1, 'm²', 'acres'), 0.000247105381);
  assert.equal(convertAgriculturalUnit(2.5, 'litres', 'millilitres'), 2500);
  assert.equal(convertAgriculturalUnit(23, 'price/kg', 'price/quintal'), 2300);
  assert.equal(convertAgriculturalUnit(2300, 'price/quintal', 'price/kg'), 23);
});

test('invalid values and unsupported unit pairs are rejected', () => {
  assert.equal(convertAgriculturalUnit(-1, 'kg', 'tonnes'), null);
  assert.equal(convertAgriculturalUnit(Number.NaN, 'kg', 'tonnes'), null);
  assert.equal(convertAgriculturalUnit(1, 'litres', 'kg'), null);
});

test('planner calendar covers whole weeks including month boundary days', () => {
  const days = monthCalendarDays('2026-10');
  assert.equal(days.length % 7, 0);
  assert.ok(days.includes('2026-10-01'));
  assert.ok(days.includes('2026-10-31'));
  assert.equal(days[0], '2026-09-27');
  assert.deepEqual(monthCalendarDays('invalid'), []);
});

test('date keys validate calendar dates without depending on local timezone', () => {
  assert.equal(isValidDateKey('2026-10-13'), true);
  assert.equal(isValidDateKey('2024-02-29'), true);
  assert.equal(isValidDateKey('2025-02-29'), false);
  assert.equal(isValidDateKey('2026-13-01'), false);
  assert.equal(isValidDateKey('2026-2-01'), false);
});

test('CSV cells quote content and neutralize spreadsheet formulas', () => {
  assert.equal(escapeCsvCell('tomato, ripe'), '"tomato, ripe"');
  assert.equal(escapeCsvCell('Farmer said "ready"'), '"Farmer said ""ready"""');
  assert.equal(escapeCsvCell('=HYPERLINK("https://example.invalid")'), '"\'=HYPERLINK(""https://example.invalid"")"');
  assert.equal(escapeCsvCell('  +SUM(1,2)'), '"\'  +SUM(1,2)"');
});
