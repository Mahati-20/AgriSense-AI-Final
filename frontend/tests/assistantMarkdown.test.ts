import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AssistantErrorMessage, AssistantMarkdown, normalizeEscapedMarkdown } from '../src/assistantMarkdown.ts';

function renderMarkdown(content: string): string {
  return renderToStaticMarkup(createElement(AssistantMarkdown, { content }));
}

test('renders Markdown headings as semantic headings', () => {
  assert.match(renderMarkdown('### Tomato Market Price Status'), /<h3>Tomato Market Price Status<\/h3>/);
});

test('renders bold and italic formatting', () => {
  const html = renderMarkdown('**Market warning** and *check the source date*.');
  assert.match(html, /<strong>Market warning<\/strong>/);
  assert.match(html, /<em>check the source date<\/em>/);
});

test('renders unordered and ordered lists', () => {
  const html = renderMarkdown('- Check the market\n- Review weather\n\n1. Wait\n2. Recheck tomorrow');
  assert.match(html, /<ul>[\s\S]*<li>Check the market<\/li>[\s\S]*<li>Review weather<\/li>[\s\S]*<\/ul>/);
  assert.match(html, /<ol>[\s\S]*<li>Wait<\/li>[\s\S]*<li>Recheck tomorrow<\/li>[\s\S]*<\/ol>/);
});

test('renders links, horizontal rules and Markdown line breaks', () => {
  const html = renderMarkdown('First line\nsecond line\n\n---\n\n[Weather source](https://example.com/weather)');
  assert.match(html, /First line\nsecond line/);
  assert.match(html, /<hr\/>|<hr>/);
  assert.match(html, /<a[^>]+href="https:\/\/example\.com\/weather"[^>]+target="_blank"[^>]+rel="noopener noreferrer"/);
});

test('normalizes escaped emphasis and list markers without stripping ordinary backslashes', () => {
  const markdown = String.raw`\*\*bold\*\* and \*italic\*` + '\n' + String.raw`\* bullet`;
  const html = renderMarkdown(markdown);
  assert.match(html, /<strong>bold<\/strong>/);
  assert.match(html, /<em>italic<\/em>/);
  assert.match(html, /<li>bullet<\/li>/);
  assert.equal(normalizeEscapedMarkdown(String.raw`C:\farm\crop`), String.raw`C:\farm\crop`);
});

test('renders realistic AgriSense market, recommendation, storage and weather details', () => {
  const response = [
    '### Tomato Market Price Status',
    String.raw`\*\*Live tomato mandi prices are unavailable\*\*. I cannot verify a current selling price.`,
    '',
    String.raw`\* \*\*Current Recommendation:\*\* \*\*WAIT\*\*`,
    '- Recheck the local mandi before selling.',
    '- Do not treat demo rates as a live quote.',
    '',
    '**Storage (demo data):** ₹1.20/kg/day. Confirm the facility rate directly.',
    '',
    '### Weather',
    'Rain is forecast; keep tomato foliage dry where practical.',
    '',
    '| Data | Status |',
    '| --- | --- |',
    '| Market | Unavailable |',
    '| Storage rate | Demo |',
  ].join('\n');
  const html = renderMarkdown(response);
  assert.match(html, /<h3>Tomato Market Price Status<\/h3>/);
  assert.match(html, /<strong>Current Recommendation:<\/strong> <strong>WAIT<\/strong>/);
  assert.match(html, /Live tomato mandi prices are unavailable/);
  assert.match(html, /Storage \(demo data\):/);
  assert.match(html, /<h3>Weather<\/h3>/);
  assert.match(html, /class="assistant-table-scroll"><table(?:\s|>)/);
  assert.doesNotMatch(html, /<table[^>]*node=/);
});

test('leaves ordinary prose and path-like text intact', () => {
  const html = renderMarkdown(String.raw`Keep this plain text and C:\farm\tomato as written.`);
  assert.match(html, /Keep this plain text and C:\\farm\\tomato as written\./);
  assert.doesNotMatch(html, /<strong>|<em>/);
});

test('treats raw HTML as text and rejects dangerous link schemes', () => {
  const html = renderMarkdown('<script>alert(1)</script> [click](javascript:alert%281%29)');
  assert.doesNotMatch(html, /<script>/i);
  assert.doesNotMatch(html, /href="javascript:/i);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /click/);
});

test('renders an explicit empty-response state', () => {
  assert.match(renderMarkdown('  '), /No response text was returned\./);
});

test('keeps error messages as safely escaped plain text', () => {
  const html = renderToStaticMarkup(createElement(AssistantErrorMessage, { message: '<img onerror=alert(1)>' }));
  assert.doesNotMatch(html, /<img /i);
  assert.match(html, /&lt;img onerror=alert\(1\)&gt;/);
});
