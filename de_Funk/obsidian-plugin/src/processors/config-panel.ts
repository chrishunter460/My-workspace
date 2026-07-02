/**
 * Config panel state store.
 *
 * A control.config block registers its id and available controls here.
 * Other exhibits with config_ref: {id} subscribe to state changes.
 */

type StateListener = (state: Record<string, unknown>) => void;

interface ConfigPanel {
  id: string;
  state: Record<string, unknown>;
  listeners: StateListener[];
}

const panels = new Map<string, ConfigPanel>();

/** Register or update a control panel. */
export function registerPanel(id: string, initialState: Record<string, unknown> = {}): void {
  if (!panels.has(id)) {
    console.log(`[config-panel] registerPanel: NEW '${id}'`);
    panels.set(id, { id, state: initialState, listeners: [] });
  } else {
    const panel = panels.get(id)!;
    console.log(`[config-panel] registerPanel: EXISTS '${id}', ${panel.listeners.length} listeners`);
    panel.state = { ...panel.state, ...initialState };
  }
}

/** Subscribe to state changes for a panel. Returns an unsubscribe function. */
export function subscribe(id: string, listener: StateListener): () => void {
  if (!panels.has(id)) {
    registerPanel(id);
  }
  const panel = panels.get(id)!;
  panel.listeners.push(listener);
  console.log(`[config-panel] subscribe: '${id}' now has ${panel.listeners.length} listener(s)`);
  return () => {
    panel.listeners = panel.listeners.filter((l) => l !== listener);
    console.log(`[config-panel] unsubscribe: '${id}' now has ${panel.listeners.length} listener(s)`);
  };
}

/** Update a control value and notify all listeners. */
export function updateControl(id: string, key: string, value: unknown): void {
  const panel = panels.get(id);
  if (!panel) {
    console.warn(`[config-panel] updateControl: panel '${id}' NOT FOUND. Known panels:`, [...panels.keys()]);
    return;
  }
  panel.state = { ...panel.state, [key]: value };
  console.log(`[config-panel] updateControl: ${id}.${key} → ${panel.listeners.length} listener(s)`);
  for (const listener of panel.listeners) {
    listener(panel.state);
  }
}

/** Set a control value WITHOUT notifying listeners (for initial state setup). */
export function setControlSilent(id: string, key: string, value: unknown): void {
  const panel = panels.get(id);
  if (!panel) return;
  panel.state = { ...panel.state, [key]: value };
}

/** Notify all listeners of current state (call after batch setControlSilent). */
export function notifyListeners(id: string): void {
  const panel = panels.get(id);
  if (!panel) return;
  console.log(`[config-panel] notifyListeners: '${id}' → ${panel.listeners.length} listener(s), state keys:`, Object.keys(panel.state));
  for (const listener of panel.listeners) listener(panel.state);
}

/** Get current state for a panel. */
export function getState(id: string): Record<string, unknown> {
  return panels.get(id)?.state ?? {};
}

/** Clear all panels (called on note switch). */
export function clearPanels(): void {
  const ids = [...panels.keys()];
  const listenerCounts = ids.map(id => `${id}:${panels.get(id)?.listeners.length ?? 0}`);
  console.log(`[config-panel] clearPanels: destroying ${ids.length} panels [${listenerCounts.join(', ')}]`);
  console.trace("[config-panel] clearPanels stack trace");
  panels.clear();
}
