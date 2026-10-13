import assert from 'node:assert/strict';
import test from 'node:test';
import { newsResultsState, presentNewsArticle } from '../src/newsUtils.ts';
import type { NewsItem } from '../src/types.ts';

const article: NewsItem = {
  id: 'gnews-1', headline: 'Tomato crop update', date: '2026-10-10T08:00:00Z',
  summary: 'A publisher report.', image: 'https://news.example/image.jpg',
  source: 'Example News', url: 'https://news.example/story', data_source: 'GNews',
};

test('successful GNews articles retain the source fields and safe article links', () => {
  const view = presentNewsArticle(article, 'en-US');
  assert.equal(view.headline, 'Tomato crop update');
  assert.equal(view.source, 'Example News');
  assert.equal(view.summary, 'A publisher report.');
  assert.equal(view.articleUrl, 'https://news.example/story');
  assert.equal(view.imageUrl, 'https://news.example/image.jpg');
  assert.ok(view.dateLabel);
});

test('empty and malformed provider fields stay empty instead of becoming invented content', () => {
  const view = presentNewsArticle({
    ...article, headline: null, source: null, summary: null, date: 'not-a-date',
    url: 'javascript:alert(1)', image: 'data:text/html,bad',
  });
  assert.equal(view.headline, 'Article title unavailable');
  assert.equal(view.source, 'News source unavailable');
  assert.equal(view.summary, null);
  assert.equal(view.dateLabel, 'not-a-date');
  assert.equal(view.articleUrl, null);
  assert.equal(view.imageUrl, null);
});

test('news page reports loading, provider error, initial prompt, empty, and results separately', () => {
  assert.equal(newsResultsState({ loading: true, error: '', hasSearched: true, articleCount: 0 }), 'loading');
  assert.equal(newsResultsState({ loading: false, error: 'GNews unavailable', hasSearched: true, articleCount: 0 }), 'error');
  assert.equal(newsResultsState({ loading: false, error: '', hasSearched: false, articleCount: 0 }), 'prompt');
  assert.equal(newsResultsState({ loading: false, error: '', hasSearched: true, articleCount: 0 }), 'empty');
  assert.equal(newsResultsState({ loading: false, error: '', hasSearched: true, articleCount: 1 }), 'results');
});
