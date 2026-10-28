import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Copy, Check, Eye, ShoppingCart } from 'lucide-react';
import ProductImage from './ProductImage';

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

/**
 * Inline Interactive Product Card rendered directly inside AI Chatbot response
 * Enables instant 1-click preview and modal popup.
 */
function InlineProductCard({ product, onViewDetail, onSelect }) {
  if (!product) return null;
  const isOutOfStock = (product.stock_quantity ?? 0) <= 0 || product.status !== 'active';

  const formatVND = (amount) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount || 0);
  };

  return (
    <div
      onClick={() => onViewDetail && onViewDetail(product)}
      style={{
        margin: '0.85rem 0 1rem 0',
        background: 'rgba(0, 0, 0, 0.35)',
        border: '1px solid var(--border-color)',
        borderRadius: '6px',
        padding: '0.75rem 1rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: 'var(--shadow-retro)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--accent-cyan)';
        e.currentTarget.style.boxShadow = '0 0 14px rgba(0, 229, 255, 0.18)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--border-color)';
        e.currentTarget.style.boxShadow = 'var(--shadow-retro)';
        e.currentTarget.style.transform = 'none';
      }}
      title="Bấm vào để xem ảnh phóng to và chi tiết sản phẩm"
    >
      {/* Left: Thumbnail Image + Hover Cue */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flex: 1, minWidth: '220px' }}>
        <div
          style={{
            width: '84px',
            height: '84px',
            borderRadius: '4px',
            overflow: 'hidden',
            background: '#0a0d14',
            border: '1px solid var(--border-color)',
            flexShrink: 0,
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <ProductImage
            src={product.image_url}
            alt={product.name}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              background: 'rgba(0, 0, 0, 0.75)',
              fontSize: '0.62rem',
              color: 'var(--accent-cyan)',
              textAlign: 'center',
              padding: '1px 0',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
            }}
          >
            [ XEM ẢNH ]
          </div>
        </div>

        {/* Center: Info */}
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem', flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: '0.72rem',
                padding: '1px 6px',
                borderRadius: '3px',
                background: 'rgba(0, 229, 255, 0.12)',
                color: 'var(--accent-cyan)',
                border: '1px solid rgba(0, 229, 255, 0.3)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
              }}
            >
              [ {product.sku} ]
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {product.category_name || product.category || 'Thiết bị'}
            </span>
          </div>

          <h5
            style={{
              margin: '0 0 0.35rem 0',
              fontSize: '0.94rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              lineHeight: 1.3,
            }}
          >
            {product.name}
          </h5>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: '1.05rem',
                fontWeight: 800,
                color: 'var(--accent-amber)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {formatVND(product.selling_price ?? product.price)}
            </span>
            <span
              style={{
                fontSize: '0.74rem',
                padding: '1px 6px',
                borderRadius: '3px',
                background: isOutOfStock ? 'rgba(248, 81, 73, 0.15)' : 'rgba(57, 211, 83, 0.15)',
                color: isOutOfStock ? 'var(--accent-red, #f85149)' : 'var(--accent-green)',
                border: `1px solid ${isOutOfStock ? 'rgba(248, 81, 73, 0.4)' : 'rgba(57, 211, 83, 0.4)'}`,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}
            >
              Kho: {product.stock_quantity ?? 0} {product.unit || 'cái'}
            </span>
          </div>
        </div>
      </div>

      {/* Right: Quick Action Buttons */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => onViewDetail && onViewDetail(product)}
          className="btn btn-secondary"
          style={{
            fontSize: '0.78rem',
            padding: '0.45rem 0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            color: 'var(--accent-cyan)',
            borderColor: 'var(--accent-cyan)',
            whiteSpace: 'nowrap',
          }}
          title="Bấm để xem ảnh chi tiết và thông số kỹ thuật"
        >
          <Eye size={13} /> Xem chi tiết
        </button>

        {onSelect && (
          <button
            type="button"
            onClick={() => onSelect(product)}
            disabled={isOutOfStock}
            className="btn btn-primary"
            style={{
              fontSize: '0.78rem',
              padding: '0.45rem 0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              background: isOutOfStock ? 'transparent' : 'var(--accent-amber)',
              borderColor: 'var(--accent-amber)',
              color: '#000',
              fontWeight: 700,
              whiteSpace: 'nowrap',
            }}
            title="Chuyển sang màn hình POS tạo đơn"
          >
            <ShoppingCart size={13} /> Mở bán POS
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Pre-processes AI markdown response to insert product preview card triggers
 * right below each product section (e.g. 1. Product Name or SKU line).
 */
export function injectProductPreviewCards(content, products = []) {
  if (!content || !products || products.length === 0) return content;

  let result = String(content);
  const injectedSkus = new Set();

  products.forEach((prod) => {
    if (!prod || !prod.sku || injectedSkus.has(prod.sku)) return;

    let matched = false;

    // Pattern 1: Numbered heading or list item with product name
    // e.g. "1. Chuột không dây Công thái học Silent M3" or "### 1. Chuột..."
    const escapedName = (prod.name || '').trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (escapedName) {
      const nameRegex = new RegExp(`(^.*(?:\\d+\\.|#+)\\s+.*?${escapedName}.*$)`, 'gim');
      if (nameRegex.test(result)) {
        result = result.replace(nameRegex, (match) => {
          if (injectedSkus.has(prod.sku)) return match;
          injectedSkus.add(prod.sku);
          return `${match}\n\n\`\`\`product-card:${prod.sku}\n\`\`\``;
        });
        matched = true;
      }
    }

    // Pattern 2: Line containing SKU label like "Mã SKU: SP-OFFICE-02"
    if (!matched) {
      const skuRegex = new RegExp(`(^.*(?:Mã SKU|SKU|Mã).*?${prod.sku}.*$)`, 'gim');
      if (skuRegex.test(result)) {
        result = result.replace(skuRegex, (match) => {
          if (injectedSkus.has(prod.sku)) return match;
          injectedSkus.add(prod.sku);
          return `${match}\n\n\`\`\`product-card:${prod.sku}\n\`\`\``;
        });
        matched = true;
      }
    }

    // Pattern 3: Any line with the bare SKU
    if (!matched) {
      const bareSkuRegex = new RegExp(`(^.*${prod.sku}.*$)`, 'gim');
      if (bareSkuRegex.test(result)) {
        result = result.replace(bareSkuRegex, (match) => {
          if (injectedSkus.has(prod.sku)) return match;
          injectedSkus.add(prod.sku);
          return `${match}\n\n\`\`\`product-card:${prod.sku}\n\`\`\``;
        });
        matched = true;
      }
    }
  });

  return result;
}

export default function MarkdownRenderer({
  content,
  className = '',
  products = [],
  onViewProduct = null,
  onSelectProduct = null,
}) {
  // Pre-process markdown to embed product-card tokens for matched products
  const processedContent = useMemo(() => {
    if (!content) return '';
    return injectProductPreviewCards(content, products);
  }, [content, products]);

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
          // Code block handling with custom header and copy button OR InlineProductCard
          pre: ({ node, children, ...props }) => {
            const childArray = React.Children.toArray(children);
            const codeChild = childArray.find(
              (child) => React.isValidElement(child) && (child.type === 'code' || child.props?.className)
            );

            if (codeChild && React.isValidElement(codeChild)) {
              const codeClassName = codeChild.props?.className || '';
              // Detect custom product-card token
              const prodCardMatch = /language-product-card(?::([A-Za-z0-9_-]+))?/.exec(codeClassName);
              if (prodCardMatch) {
                const sku = prodCardMatch[1] || String(codeChild.props?.children || '').trim();
                const matchedProduct = (products || []).find(
                  (p) => p.sku === sku || String(p.id) === sku || String(p.product_id) === sku
                );
                if (matchedProduct) {
                  return (
                    <InlineProductCard
                      product={matchedProduct}
                      onViewDetail={onViewProduct}
                      onSelect={onSelectProduct}
                    />
                  );
                }
              }

              return (
                <CodeBlock className={codeClassName} {...props}>
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
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}

