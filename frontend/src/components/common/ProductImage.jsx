import React, { useState } from 'react';

/**
 * ProductImage Component
 * Handles image rendering with fallback for missing or broken image URLs.
 * Matches StoreFlow AI's retro-futuristic dark neon aesthetic.
 */
export default function ProductImage({
  src,
  alt = 'Sản phẩm',
  className = '',
  style = {},
  placeholderIcon = '📦'
}) {
  const [error, setError] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Normalize image URL: handle backend upload paths or external URLs
  const resolvedSrc = src && src.trim() !== '' ? src.trim() : null;

  if (!resolvedSrc || error) {
    return (
      <div
        className={`product-img-fallback ${className}`}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-input)',
          border: '1px dashed var(--border-default)',
          color: 'var(--amber-primary)',
          fontSize: '1.25rem',
          userSelect: 'none',
          borderRadius: 'inherit',
          ...style,
        }}
        title={alt}
      >
        <span style={{ fontSize: '1.4em', filter: 'drop-shadow(0 0 4px var(--amber-glow))' }}>
          {placeholderIcon}
        </span>
        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px', fontWeight: 600 }}>
          NO IMAGE
        </span>
      </div>
    );
  }

  return (
    <div
      className={`product-img-wrapper ${className}`}
      style={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 'inherit',
        background: 'var(--bg-input)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...style,
      }}
    >
      <img
        src={resolvedSrc}
        alt={alt}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: style?.objectFit || 'cover',
          display: 'block',
          opacity: loaded ? 1 : 0.4,
          transition: 'opacity 0.25s ease, transform 0.3s ease',
        }}
      />
    </div>
  );
}
