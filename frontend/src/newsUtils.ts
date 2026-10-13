import type { NewsItem } from './types';

export type NewsResultsState = 'loading' | 'error' | 'prompt' | 'empty' | 'results';

export function newsResultsState(input: {
  loading: boolean;
  error: string;
  hasSearched: boolean;
  articleCount: number;
}): NewsResultsState {
  if (input.loading) return 'loading';
  if (input.error) return 'error';
  if (!input.hasSearched) return 'prompt';
  if (input.articleCount === 0) return 'empty';
  return 'results';
}

function safeWebUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : null;
  } catch {
    return null;
  }
}

export function presentNewsArticle(item: NewsItem, locale?: string) {
  let dateLabel = item.date;
  if (item.date) {
    const parsedDate = new Date(item.date);
    if (!Number.isNaN(parsedDate.getTime())) {
      dateLabel = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(parsedDate);
    }
  }
  return {
    headline: item.headline || 'Article title unavailable',
    source: item.source || 'News source unavailable',
    summary: item.summary || null,
    dateLabel,
    articleUrl: safeWebUrl(item.url),
    imageUrl: safeWebUrl(item.image),
  };
}
