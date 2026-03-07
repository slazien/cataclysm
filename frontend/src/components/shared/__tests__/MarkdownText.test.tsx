import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MarkdownText } from '../MarkdownText';

describe('MarkdownText', () => {
  describe('inline mode (default)', () => {
    it('renders plain text', () => {
      render(<MarkdownText>Hello world</MarkdownText>);
      expect(screen.getByText('Hello world')).toBeInTheDocument();
    });

    it('renders bold text with <strong>', () => {
      const { container } = render(<MarkdownText>**bold text**</MarkdownText>);
      const strong = container.querySelector('strong');
      expect(strong).toBeInTheDocument();
      expect(strong?.textContent).toBe('bold text');
    });

    it('renders italic text with <em>', () => {
      const { container } = render(<MarkdownText>*italic text*</MarkdownText>);
      const em = container.querySelector('em');
      expect(em).toBeInTheDocument();
      expect(em?.textContent).toBe('italic text');
    });

    it('renders inline code with <code>', () => {
      const { container } = render(<MarkdownText>`some code`</MarkdownText>);
      const code = container.querySelector('code');
      expect(code).toBeInTheDocument();
      expect(code?.textContent).toBe('some code');
    });

    it('does not wrap content in <p> tags (inline mode strips them)', () => {
      const { container } = render(<MarkdownText>No paragraph wrapping</MarkdownText>);
      const p = container.querySelector('p');
      expect(p).not.toBeInTheDocument();
    });

    it('renders links as <a> elements', () => {
      render(<MarkdownText>[click here](https://example.com)</MarkdownText>);
      const link = screen.getByRole('link', { name: 'click here' });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('strips disallowed block-level elements like headings', () => {
      const { container } = render(<MarkdownText># Heading</MarkdownText>);
      const h1 = container.querySelector('h1');
      expect(h1).not.toBeInTheDocument();
      // Content should still appear as text (unwrapped)
      expect(screen.getByText('Heading')).toBeInTheDocument();
    });
  });

  describe('block mode', () => {
    it('renders paragraphs with <p> tags', () => {
      const { container } = render(<MarkdownText block>A paragraph</MarkdownText>);
      const p = container.querySelector('p');
      expect(p).toBeInTheDocument();
      expect(p?.textContent).toBe('A paragraph');
    });

    it('paragraphs have mb-2 spacing class', () => {
      const { container } = render(<MarkdownText block>Text here</MarkdownText>);
      const p = container.querySelector('p');
      expect(p?.className).toContain('mb-2');
    });

    it('renders unordered lists', () => {
      const { container } = render(
        <MarkdownText block>{'- item 1\n- item 2\n- item 3'}</MarkdownText>,
      );
      const ul = container.querySelector('ul');
      expect(ul).toBeInTheDocument();
      expect(ul?.className).toContain('list-disc');
      const items = container.querySelectorAll('li');
      expect(items.length).toBe(3);
    });

    it('renders ordered lists', () => {
      const { container } = render(
        <MarkdownText block>{'1. first\n2. second\n3. third'}</MarkdownText>,
      );
      const ol = container.querySelector('ol');
      expect(ol).toBeInTheDocument();
      expect(ol?.className).toContain('list-decimal');
    });

    it('list items have mb-1 class', () => {
      const { container } = render(
        <MarkdownText block>{'- item one\n- item two'}</MarkdownText>,
      );
      const li = container.querySelector('li');
      expect(li?.className).toContain('mb-1');
    });

    it('renders bold text inside block mode', () => {
      const { container } = render(<MarkdownText block>**bold block**</MarkdownText>);
      const strong = container.querySelector('strong');
      expect(strong).toBeInTheDocument();
    });

    it('renders italic text inside block mode', () => {
      const { container } = render(<MarkdownText block>*italic block*</MarkdownText>);
      const em = container.querySelector('em');
      expect(em).toBeInTheDocument();
    });

    it('strips disallowed elements like headings in block mode', () => {
      const { container } = render(<MarkdownText block># Heading</MarkdownText>);
      const h1 = container.querySelector('h1');
      expect(h1).not.toBeInTheDocument();
      // Content still appears (unwrapped)
      expect(screen.getByText('Heading')).toBeInTheDocument();
    });
  });
});
