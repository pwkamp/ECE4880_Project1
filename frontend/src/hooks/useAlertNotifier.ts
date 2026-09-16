import { useEffect, useRef, useState } from 'react';
import type { AlertEvent } from '../lib/alertEngine';
import { notifyAlert, type DeliveryResult } from '../lib/notifyClient';

export type DeliveryState = 'pending' | DeliveryResult;

/**
 * Delivers HIGH/LOW alert events to the backend exactly once each and tracks
 * their per-event delivery status for display. Recovery (NORMAL) events are
 * ignored. Never throws.
 */
export function useAlertNotifier(events: AlertEvent[]): Record<string, DeliveryState> {
  const dispatched = useRef<Set<string>>(new Set());
  const [statuses, setStatuses] = useState<Record<string, DeliveryState>>({});

  useEffect(() => {
    for (const event of events) {
      if (event.transition !== 'HIGH' && event.transition !== 'LOW') continue;
      if (dispatched.current.has(event.id)) continue;
      dispatched.current.add(event.id);
      setStatuses((prev) => ({ ...prev, [event.id]: 'pending' }));
      void notifyAlert(event).then((result) => {
        setStatuses((prev) => ({ ...prev, [event.id]: result }));
      });
    }
  }, [events]);

  return statuses;
}
