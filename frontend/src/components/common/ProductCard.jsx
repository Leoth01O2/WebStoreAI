import React from 'react';
import { Eye, ShoppingCart, CheckCircle, Layers, Info, AlertCircle } from 'lucide-react';
import ProductImage from './ProductImage';
import { StockBadge } from '../ui/Badge';

/**
 * Reusable Interactive Equal-Height Product Card for StoreFlow AI
 * Used in Chatbot RAG Recommendations and Image Search Results.
 * Strictly adheres to SQLite Truth Guard: displaying real price, stock, and status.
 */
export default function ProductCard({
  product,
  onViewDetail,
  onSelect,
  actionLabel = 'Mở bán POS',
  compact = false,
  showRelationship = false,
  renderRelationshipBadge = null,
}) {
  if (!product) return null;

  const formatVND = (amount) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount || 0);
  };

  const isOutOfStock = (product.stock_quantity ?? 0) <= 0 || product.status !== 'active';
  const price = product.selling_price ?? product.price ?? 0;
  const category = product.category_name || product.category || 'Công nghệ';

  const defaultRelationshipBadge = (rel, prod = product) => {
    const norm = String(rel || prod?.relationship || '').toUpperCase().trim();
    const hasSqliteData = Boolean(
      prod?.sku &&
      ((prod?.stock_quantity !== undefined && prod?.stock_quantity !== null) ||
       prod?.selling_price !== undefined ||
       prod?.price !== undefined)
    );

    const baseBadgeStyle = {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      fontSize: '0.75rem',
      padding: '2px 8px',
      borderRadius: '3px',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      whiteSpace: 'nowrap',
      flexShrink: 0,
    };

    switch (norm) {
      case 'MATCH':
        return (
          <span
            style={{
              ...baseBadgeStyle,
              background: 'rgba(57, 211, 83, 0.15)',
              color: 'var(--accent-green)',
              border: '1px solid rgba(57, 211, 83, 0.4)',
            }}
          >
            <CheckCircle size={12} /> [ KHỚP SẢN PHẨM ]
          </span>
        );
      case 'SIMILAR':
        return (
          <span
            style={{
              ...baseBadgeStyle,
              background: 'rgba(0, 229, 255, 0.15)',
              color: 'var(--accent-cyan)',
              border: '1px solid rgba(0, 229, 255, 0.4)',
            }}
          >
            <Layers size={12} /> [ SẢN PHẨM TƯƠNG TỰ ]
          </span>
        );
      case 'RELATED':
        return (
          <span
            style={{
              ...baseBadgeStyle,
              background: 'rgba(255, 180, 84, 0.15)',
              color: 'var(--accent-amber)',
              border: '1px solid rgba(255, 180, 84, 0.4)',
            }}
          >
            <Info size={12} /> [ CÙNG NHÓM HÀNG ]
          </span>
        );
      default:
        if (hasSqliteData || (prod && prod.sku)) {
          return (
            <span
              style={{
                ...baseBadgeStyle,
                background: 'rgba(57, 211, 83, 0.15)',
                color: 'var(--accent-green)',
                border: '1px solid rgba(57, 211, 83, 0.4)',
              }}
            >
              <CheckCircle size={12} /> [ ĐÃ ĐỐI CHIẾU ]
            </span>
          );
        }
        return (
          <span
            style={{
              ...baseBadgeStyle,
              background: 'rgba(248, 81, 73, 0.15)',
              color: 'var(--accent-red, #f85149)',
              border: '1px solid rgba(248, 81, 73, 0.4)',
            }}
          >
            <AlertCircle size={12} /> [ KHÔNG TÌM THẤY ]
          </span>
        );
    }
  };

  const reasonText = product.reason || product.match_reason || product.ineligible_reason;

  return (
    <div
      style={{
        background: 'var(--panel-bg)',
        border: '1px solid var(--border-color)',
        borderRadius: '6px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        boxShadow: 'var(--shadow-retro)',
        transition: 'transform 0.15s ease, border-color 0.15s ease',
        height: '100%',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        {/* Header with Relationship or Category */}
        <div
          style={{
            padding: '0.55rem 0.85rem',
            borderBottom: '1px solid var(--border-color)',
            background: 'rgba(0, 0, 0, 0.25)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          {showRelationship && (product.relationship || product.sku) ? (
            renderRelationshipBadge
              ? renderRelationshipBadge(product.relationship, product)
              : defaultRelationshipBadge(product.relationship, product)
          ) : (
            <span
              style={{
                fontSize: '0.72rem',
                color: 'var(--accent-cyan)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                letterSpacing: '0.03em',
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              [ {product.sku || 'SKU'} ]
            </span>
          )}
          <span
            style={{
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '120px',
              textAlign: 'right',
            }}
            title={category}
          >
            {category}
          </span>
        </div>

        {/* Product Image & Info */}
        <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', flex: 1 }}>
          <div
            style={{
              height: '150px',
              borderRadius: '4px',
              overflow: 'hidden',
              background: '#ffffff',
              border: '1px solid var(--border-color)',
              marginBottom: '0.75rem',
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
          </div>

          <h4
            style={{
              margin: '0 0 0.4rem 0',
              fontSize: '0.92rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              lineHeight: '1.4em',
              minHeight: '2.8em',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
            title={product.name}
          >
            {product.name}
          </h4>

          {/* Single Stock Row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
              Kho: {product.stock_quantity ?? 0} {product.unit || 'cái'}
            </span>
            <StockBadge stock={product.stock_quantity ?? 0} status={product.status || 'active'} />
          </div>

          {/* Single Price Row */}
          <div
            style={{
              fontSize: '1.05rem',
              fontWeight: 800,
              color: 'var(--accent-amber)',
              fontFamily: 'var(--font-mono)',
              marginBottom: '0.5rem',
            }}
          >
            {formatVND(price)}
          </div>

          {/* Reason or Description Box (Equal-Height with flex-grow: 1, minHeight: 54px) */}
          <div
            style={{
              flexGrow: 1,
              minHeight: '54px',
              padding: '0.45rem 0.65rem',
              borderRadius: '4px',
              background: 'rgba(0, 0, 0, 0.25)',
              border: '1px solid var(--border-color)',
              fontSize: '0.76rem',
              color: 'var(--text-muted)',
              lineHeight: '1.35',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              marginBottom: '0.5rem',
            }}
            title={reasonText || product.description || ''}
          >
            {reasonText ? (
              <>
                <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>Đối chiếu: </span>
                {reasonText}
              </>
            ) : product.description ? (
              product.description
            ) : (
              'Thông tin sản phẩm đã đối chiếu từ SQLite.'
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons (Aligned to bottom) */}
      <div
        style={{
          marginTop: 'auto',
          padding: '0.65rem 0.85rem',
          borderTop: '1px solid var(--border-color)',
          background: 'rgba(0, 0, 0, 0.15)',
          display: 'flex',
          gap: '0.5rem',
        }}
      >
        {onViewDetail && (
          <button
            type="button"
            onClick={() => onViewDetail(product)}
            className="btn btn-secondary"
            style={{
              flex: 1,
              fontSize: '0.78rem',
              padding: '0.4rem 0.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              whiteSpace: 'nowrap',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
            }}
          >
            <Eye size={13} /> CHI TIẾT
          </button>
        )}

        {onSelect && (
          <button
            type="button"
            onClick={() => onSelect(product)}
            disabled={isOutOfStock}
            className="btn btn-secondary"
            style={{
              flex: 1,
              fontSize: '0.78rem',
              padding: '0.4rem 0.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              color: isOutOfStock ? 'var(--text-muted)' : 'var(--accent-amber)',
              cursor: isOutOfStock ? 'not-allowed' : 'pointer',
              opacity: isOutOfStock ? 0.5 : 1,
              whiteSpace: 'nowrap',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
            }}
            title={isOutOfStock ? 'Sản phẩm tạm thời hết hàng' : actionLabel}
          >
            <ShoppingCart size={13} /> {isOutOfStock ? 'HẾT HÀNG' : (actionLabel ? actionLabel.toUpperCase() : 'MỞ BÁN POS')}
          </button>
        )}
      </div>
    </div>
  );
}
