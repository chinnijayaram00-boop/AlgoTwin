import { CELL_TONES } from "./algorithmService";

/**
 * Draw one frame.
 *
 * One renderer for four layouts. The API sends the same state shape whatever the
 * algorithm is, so the branch here is on `state.kind` and never on which algorithm
 * is running -- which is what keeps "add an algorithm" a backend-only change.
 *
 * The one rule this component enforces beyond drawing is the unknown-tone fallback.
 * `toneClass` returns the idle class for a tone it does not recognise, so a backend
 * that adds a tone without a matching style here shows an unhighlighted cell rather
 * than an element with no class at all. That is a visible, debuggable state; an
 * unhandled tone that throws would take the whole timeline down over one cell.
 */

/** The class suffix for a cell tone, defaulting to idle for anything unknown. */
export function toneClass(tone) {
  return CELL_TONES.includes(tone) ? tone : "idle";
}

/**
 * How tall a bar should be, as a percentage of the tallest value in the row.
 *
 * Bars encode magnitude, so they need a shared scale -- otherwise a run of values
 * around 500 and a run of values around 5 look identical, which is exactly the kind
 * of misleading picture this feature is supposed to avoid. The floor keeps a row of
 * equal non-zero values visible instead of collapsing them to nothing.
 */
function barHeights(cells) {
  const numbers = cells
    .map((cell) => Number(cell.label))
    .filter((value) => Number.isFinite(value));
  const highest = Math.max(0, ...numbers);
  if (highest <= 0) return cells.map(() => 8);
  return cells.map((cell) => {
    const value = Number(cell.label);
    const magnitude = Number.isFinite(value) ? Math.max(0, value) : 0;
    return Math.max(8, Math.round((magnitude / highest) * 100));
  });
}

export function FrameRenderer({ frame, stateKind }) {
  if (!frame || !frame.state) return null;
  const { rows, auxiliary, pointers, status } = frame.state;
  const kind = stateKind || frame.state.kind;

  return (
    <div className={`frame-view frame-${kind}`} data-status={status}>
      <RowGroup rows={rows} pointers={pointers} kind={kind} primary />
      {auxiliary && auxiliary.length ? (
        <div className="frame-auxiliary">
          <span className="frame-auxiliary-label">Working structures</span>
          <RowGroup rows={auxiliary} pointers={{}} kind={kind} />
        </div>
      ) : null}
    </div>
  );
}

function RowGroup({ rows, pointers, kind, primary = false }) {
  if (!rows || !rows.length) return null;
  return (
    <div className={primary ? "frame-rows" : "frame-rows frame-rows-compact"}>
      {rows.map((row, rowIndex) => (
        <Row key={`${row.label}-${rowIndex}`} row={row} pointers={pointers} kind={kind} />
      ))}
    </div>
  );
}

function Row({ row, pointers, kind }) {
  const cells = row.cells || [];
  const height = kind === "bar_array" ? barHeights(cells) : null;

  return (
    <div className="frame-row">
      <span className="frame-row-label">{row.label}</span>
      <div className="frame-cells" role="list">
        {cells.map((cell, position) => {
          // A pointer mark only renders on the primary row, because a pointer is an
          // index into the structure the learner is looking at, not into every
          // auxiliary one.
          const marked = primaryMarker(pointers, position);
          return (
            <div
              aria-label={cell.label}
              className={`frame-cell tone-${toneClass(cell.tone)}${marked ? " is-pointed" : ""}`}
              data-tone={cell.tone}
              key={`${row.label}-${position}-${cell.label}`}
              role="listitem"
              style={height ? { height: `${height[position]}%` } : undefined}
              title={cell.detail || cell.label}
            >
              <span className="frame-cell-label">{cell.label}</span>
              {cell.detail ? <span className="frame-cell-detail">{cell.detail}</span> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Whether a cell carries any pointer mark.
 *
 * Pointer *names* are not drawn on the cell -- eight overlapping badges would be
 * unreadable -- so a pointer shows as a marker on the cells it occupies. The names
 * are listed next to the frame instead, where they can be read without covering
 * the thing they point at.
 */
function primaryMarker(pointers, position) {
  return Object.values(pointers || {}).some((value) => Number(value) === position);
}

/** The pointer names and what they currently hold, for the frame's side panel. */
export function PointerReadout({ pointers }) {
  const entries = Object.entries(pointers || {});
  if (!entries.length) return null;
  return (
    <div className="pointer-readout">
      <span className="pointer-readout-label">Pointers</span>
      <div className="pointer-chips">
        {entries.map(([name, position]) => (
          <span className="pointer-chip" key={name}>
            <code>{name}</code>
            <span>{position}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** The counters the algorithm recorded, and what an absent counter means. */
export function MetricReadout({ metrics }) {
  const entries = Object.entries(metrics || {});
  if (!entries.length) return null;
  return (
    <div className="metric-readout">
      <span className="pointer-readout-label">Operations</span>
      <div className="metric-chips">
        {entries.map(([name, value]) => (
          <span className="metric-chip" key={name}>
            <code>{name.replace(/_/g, " ")}</code>
            <strong>{value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}
