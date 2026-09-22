import React, { useState } from 'react';

export const RetroChart = ({ data = [], height = 260 }) => {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        [KHÔNG CÓ DỮ LIỆU BIẾN ĐỘNG DOANH THU]
      </div>
    );
  }

  const padding = { top: 30, right: 30, bottom: 40, left: 75 };
  const width = 800; // SVG internal coordinate width

  const maxVal = Math.max(...data.map((d) => d.revenue), 1000000);
  const minVal = 0;

  const getX = (index) => {
    const availableWidth = width - padding.left - padding.right;
    return padding.left + (index / (data.length - 1 || 1)) * availableWidth;
  };

  const getY = (val) => {
    const availableHeight = height - padding.top - padding.bottom;
    return height - padding.bottom - ((val - minVal) / (maxVal - minVal)) * availableHeight;
  };

  // Generate SVG Path
  const points = data.map((d, i) => `${getX(i)},${getY(d.revenue)}`).join(' ');
  const areaPoints = `${getX(0)},${height - padding.bottom} ${points} ${getX(data.length - 1)},${height - padding.bottom}`;

  const formatCurrency = (val) => {
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M đ`;
    if (val >= 1000) return `${(val / 1000).toFixed(0)}k đ`;
    return `${val} đ`;
  };

  // Y-axis grid lines (4 ticks)
  const yTicks = [0, maxVal * 0.33, maxVal * 0.66, maxVal];

  return (
    <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
      >
        <defs>
          <linearGradient id="retroGlowGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="var(--green-terminal)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--green-terminal)" stopOpacity="0.0" />
          </linearGradient>
          <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Y Grid Lines */}
        {yTicks.map((tick, i) => {
          const y = getY(tick);
          return (
            <g key={i}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="var(--border-subtle)"
                strokeDasharray="4 4"
                strokeWidth="1"
              />
              <text
                x={padding.left - 10}
                y={y + 4}
                fill="var(--text-muted)"
                fontSize="11"
                fontFamily="var(--font-mono)"
                textAnchor="end"
              >
                {formatCurrency(tick)}
              </text>
            </g>
          );
        })}

        {/* Area fill under curve */}
        <polygon points={areaPoints} fill="url(#retroGlowGrad)" />

        {/* Connecting Line */}
        <polyline
          fill="none"
          stroke="var(--green-terminal)"
          strokeWidth="2.5"
          points={points}
          filter="url(#neonGlow)"
        />

        {/* Data Points */}
        {data.map((d, i) => {
          const cx = getX(i);
          const cy = getY(d.revenue);
          const isHovered = hoveredPoint?.index === i;

          return (
            <g key={i}>
              <circle
                cx={cx}
                cy={cy}
                r={isHovered ? 6 : 4}
                fill={isHovered ? 'var(--amber-primary)' : 'var(--bg-app)'}
                stroke={isHovered ? '#fff' : 'var(--green-terminal)'}
                strokeWidth="2"
                style={{ cursor: 'pointer', transition: 'all 0.15s' }}
                onMouseEnter={() => setHoveredPoint({ ...d, index: i, x: cx, y: cy })}
                onMouseLeave={() => setHoveredPoint(null)}
              />
              {/* X Axis Labels */}
              <text
                x={cx}
                y={height - padding.bottom + 20}
                fill={isHovered ? 'var(--amber-primary)' : 'var(--text-secondary)'}
                fontSize="11"
                fontFamily="var(--font-mono)"
                textAnchor="middle"
              >
                {d.date.substring(5)} {/* MM-DD */}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Floating Retro Tooltip */}
      {hoveredPoint && (
        <div
          style={{
            position: 'absolute',
            left: `${(hoveredPoint.x / width) * 100}%`,
            top: `${(hoveredPoint.y / height) * 100}%`,
            transform: 'translate(-50%, -125%)',
            background: 'var(--bg-card)',
            border: '1px solid var(--amber-primary)',
            padding: '0.4rem 0.75rem',
            borderRadius: 'var(--radius-xs)',
            boxShadow: 'var(--shadow-retro-lg)',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 10,
          }}
        >
          <div style={{ color: 'var(--amber-light)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
            {hoveredPoint.date}
          </div>
          <div style={{ color: 'var(--green-light)', fontWeight: 'bold', fontSize: '0.9rem', fontFamily: 'var(--font-mono)' }}>
            {Number(hoveredPoint.revenue).toLocaleString('vi-VN')} đ
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
            {hoveredPoint.order_count || 0} đơn hoàn tất
          </div>
        </div>
      )}
    </div>
  );
};
