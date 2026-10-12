import { createElement, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

/** Normalize only paired escaped emphasis markers and escaped list markers. */
export function normalizeEscapedMarkdown(markdown: string): string {
  return markdown
    .replace(/^(\s*)\\([*+-])(?=\s)/gm, '$1$2')
    .replace(/^(\s*)(\d+)\\\.(?=\s)/gm, '$1$2.')
    .replace(/\\\*\\\*([\s\S]+?)\\\*\\\*/g, '**$1**')
    .replace(/\\_\\_([\s\S]+?)\\_\\_/g, '__$1__')
    .replace(/\\\*([^*\n]+?)\\\*/g, '*$1*')
    .replace(/\\_([^_\n]+?)\\_/g, '_$1_');
}

function safeHref(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const href = value.trim();
  if (!href || href.startsWith('//')) return undefined;
  if (/^(https?:|mailto:)/i.test(href)) return href;
  if (/^(#|\/|\.\.?\/)/.test(href)) return href;
  return undefined;
}

const markdownComponents: Components = {
  a: ({ href, children, node: _node, ...props }) => {
    const safe = safeHref(href);
    if (!safe) return createElement('span', props, children);
    return createElement('a', { ...props, href: safe, target: '_blank', rel: 'noopener noreferrer' }, children);
  },
  table: ({ children, node: _node, ...props }) => createElement(
    'div',
    { className: 'assistant-table-scroll' },
    createElement('table', props, children),
  ),
  img: () => null,
};

export function AssistantMarkdown({ content }: { content: string }): ReactNode {
  if (!content.trim()) {
    return createElement('p', { className: 'assistant-empty-response' }, 'No response text was returned.');
  }

  return createElement(
    'div',
    { className: 'assistant-markdown' },
    createElement(ReactMarkdown, {
      remarkPlugins: [remarkGfm],
      // react-markdown does not parse raw HTML; constrain generated URLs as well.
      urlTransform: (url: string) => safeHref(url) ?? '',
      components: markdownComponents,
    }, normalizeEscapedMarkdown(content)),
  );
}

export function AssistantErrorMessage({ message }: { message: string }): ReactNode {
  return createElement('span', { className: 'assistant-error-message' }, message);
}
