/**
 * Global event bus for note-level filter and control changes.
 *
 * When a sidebar filter or control changes, main.ts calls the appropriate
 * notify function. Each active de_funk block subscribes via
 * subscribeToFilterChanges() so it can re-run its render() closure.
 */

type Callback = () => void;
const _subscribers = new Set<Callback>();

/** Register a render callback to be called when any note filter changes. */
export function subscribeToFilterChanges(cb: Callback): () => void {
  _subscribers.add(cb);
  return () => _subscribers.delete(cb);
}

/** Fire all registered render callbacks (called by main.ts on filter change). */
export function notifyFilterChanged(): void {
  for (const cb of _subscribers) {
    cb();
  }
}

/** Fire all render callbacks for control changes. Same bus, same effect. */
export function notifyControlChanged(): void {
  for (const cb of _subscribers) {
    cb();
  }
}
