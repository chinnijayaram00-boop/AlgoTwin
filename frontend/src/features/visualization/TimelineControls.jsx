import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";

import { SPEEDS } from "./useFrameTimeline";

/**
 * The playback controls under a rendered frame.
 *
 * The timeline state is owned by the page, not by this component, and passed in as
 * one object. That is deliberate: the page has to render the *current* frame, so if
 * this component held the index then the renderer would need it lifted back up here
 * anyway -- and a second copy of the position is exactly the copy that eventually
 * disagrees with the first.
 *
 * Every disabled state is therefore derived from the same index the renderer uses.
 * Back is disabled exactly when the cursor is on frame 0, Forward exactly when it is
 * on the last one, and neither can be wrong.
 */
export function TimelineControls({ timeline, explanation }) {
  const { index, total, playing, speedIndex } = timeline;

  return (
    <div className="timeline-controls">
      <div className="timeline-transport">
        <button
          aria-label="Restart from the first frame"
          className="button button-quiet"
          disabled={!timeline.hasFrames}
          onClick={timeline.restart}
          type="button"
        >
          <RotateCcw size={15} />
        </button>
        <button
          aria-label="Previous frame"
          className="button button-quiet"
          disabled={!timeline.canStepBackward}
          onClick={timeline.stepBackward}
          type="button"
        >
          <SkipBack size={15} />
        </button>
        <button
          aria-label={playing ? "Pause" : "Play"}
          className="button button-primary"
          disabled={!timeline.hasFrames}
          onClick={timeline.togglePlay}
          type="button"
        >
          {playing ? <Pause size={15} /> : <Play size={15} />}
          <span>{playing ? "Pause" : "Play"}</span>
        </button>
        <button
          aria-label="Next frame"
          className="button button-quiet"
          disabled={!timeline.canStepForward}
          onClick={timeline.stepForward}
          type="button"
        >
          <SkipForward size={15} />
        </button>
      </div>

      <label className="timeline-scrubber">
        <span className="sr-only">Frame</span>
        <input
          aria-label="Frame"
          disabled={!timeline.hasFrames}
          max={total ? total - 1 : 0}
          min={0}
          onChange={(event) => timeline.goTo(Number(event.target.value))}
          type="range"
          value={timeline.hasFrames ? index : 0}
        />
        <span className="timeline-position">
          Frame {total ? index + 1 : 0} of {total}
        </span>
      </label>

      <div className="timeline-speed" role="group" aria-label="Playback speed">
        {SPEEDS.map((speed, position) => (
          <button
            aria-pressed={speedIndex === position}
            className={`speed-button${speedIndex === position ? " is-active" : ""}`}
            key={speed.label}
            onClick={() => timeline.setSpeedIndex(position)}
            type="button"
          >
            {speed.label}
          </button>
        ))}
      </div>

      <p className="timeline-explanation">{explanation}</p>
    </div>
  );
}
