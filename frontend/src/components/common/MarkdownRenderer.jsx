import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Copy, Check } from 'lucide-react';

function CodeBlock({ className, children, ...props }) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';
  const codeText = String(children).replace(/\n$/, '');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback if clipboard API unavailable
    }
  };

  return (
    <div className="markdown-code-block">
      <div className="markdown-code-header">
        <span className="markdown-code-lang">{language ? language.toUpperCase() : 'CODE'}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="markdown-code-copy-btn"
          title="Sao chép mã"
          aria-label="Sao chép mã"
        >
          {copied ? <Check size={13} color="var(--accent-green)" /> : <Copy size={13} />}
          <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
        </button>
      </div>
      <pre className="markdown-pre">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}

export default function MarkdownRenderer({ content, className = '' }) {
  if (!content) return null;

  return (
    <div className={`markdown-content ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          // Responsive wrapper around tables
          table: ({ node, ...props }) => (
            <div className="markdown-table-wrapper">
              <table className="markdown-table" {...props} />
            </div>
          ),
          // Code block handling with custom header and copy button
          pre: ({ node, children, ...props }) => {
            const childArray = React.Children.toArray(children);
            const codeChild = childArray.find(
              (child) => React.isValidElement(child) && (child.type === 'code' || child.props?.className)
            );

            if (codeChild && React.isValidElement(codeChild)) {
              return (
                <CodeBlock className={codeChild.props.className} {...props}>
                  {codeChild.props.children}
                </CodeBlock>
              );
            }

            return (
              <div className="markdown-code-block">
                <pre className="markdown-pre" {...props}>
                  {children}
                </pre>
              </div>
            );
          },
          // Inline code styling
          code: ({ node, className, children, ...props }) => {
            return (
              <code className="markdown-inline-code" {...props}>
                {children}
              </code>
            );
          },
          // Safe external links
          a: ({ node, href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="markdown-link"
              {...props}
            >
              {children}
            </a>
          ),
        }}
      >
        {String(content)}
      </ReactMarkdown>
    </div>
  );
}
