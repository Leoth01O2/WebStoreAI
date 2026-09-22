import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

export const ThemeToggle = ({ className = '', showLabel = false, compact = false }) => {
  const { theme, toggleTheme, isDark } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`theme-toggle-btn ${compact ? 'theme-toggle-compact' : ''} ${className}`}
      title={isDark ? 'Chuyển sang giao diện Sáng (Vintage Editorial)' : 'Chuyển sang giao diện Tối (Retro CRT Slate)'}
      aria-label={isDark ? 'Chuyển sang giao diện Sáng' : 'Chuyển sang giao diện Tối'}
    >
      <span className="theme-toggle-indicator">
        {isDark ? (
          <Sun size={15} style={{ color: 'var(--amber-primary)' }} />
        ) : (
          <Moon size={15} style={{ color: 'var(--blue-cyber)' }} />
        )}
      </span>
      {showLabel && (
        <span className="theme-toggle-text">
          {isDark ? 'Sáng (Vintage)' : 'Tối (Retro CRT)'}
        </span>
      )}
    </button>
  );
};
