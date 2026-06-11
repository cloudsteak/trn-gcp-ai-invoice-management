// Státusz jelző badge komponens – ok / warning / error vizuális megjelenítés
import React from 'react';

const STATUS_CONFIG = {
  ok: {
    icon: '✅',
    label: 'Rendben',
    classes: 'bg-green-100 text-green-800 border-green-200',
  },
  warning: {
    icon: '⚠️',
    label: 'Figyelmeztetés',
    classes: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  },
  error: {
    icon: '❌',
    label: 'Hiba',
    classes: 'bg-red-100 text-red-800 border-red-200',
  },
};

/**
 * Props:
 *   status   – 'ok' | 'warning' | 'error'
 *   iconOnly – csak ikont jelenít meg, szöveg nélkül
 */
function StatusBadge({ status, iconOnly = false }) {
  const config = STATUS_CONFIG[status] || {
    icon: '❓',
    label: status,
    classes: 'bg-gray-100 text-gray-600 border-gray-200',
  };

  if (iconOnly) {
    return <span title={config.label}>{config.icon}</span>;
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${config.classes}`}
    >
      {config.icon} {config.label}
    </span>
  );
}

export default StatusBadge;
