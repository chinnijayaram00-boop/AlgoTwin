import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/**
 * The speeds the scrubber offers, in milliseconds between frames.
 *
 * A fixed ladder rather than a free slider: the interesting step in a merge is
 * about 700ms -- long enough to read the sentence, short enough that fourteen of
 * them do not become a wait -- and a continuous control would spend most of its
 * travel in a range nobody wants.
 */
export const SPEEDS = [
  { label: "0.5x", intervalMs: 1400 },
  { label: "1x", intervalMs: 700 },
  { label: "2x", intervalMs: 350 },
  { label: "4x", intervalMs: 160 },
];

export const DEFAULT_SPEED_INDEX = 1;

/**
 * Drive a frame timeline: play, pause, step, scrub.
 *
 * The index is the single piece of state. Everything else is derived from it, which
 * is what makes the transport buttons safe to derive too: "can I go back" is
 * `index > 0` and cannot drift from where the cursor actually is. A hook that kept
 * a separate `playing` flag *and* a separate `index` would eventually disagree, and
 * the symptom would be a Back button that does nothing on frame 3.
 *
 * Reaching the end stops playback rather than looping. A loop would be defensible
 * for a demo and wrong here: the learner pressed Play to watch an algorithm finish,
 * and restarting it without being asked hides the fact that it finished.
 */
export function useFrameTimeline(frameCount, options = {}) {
  const {
    autoplay = false,
    speedIndex = DEFAULT_SPEED_INDEX,
    onComplete,
  } = options;

  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(speedIndex);
  const [completed, setCompleted] = useState(false);

  // The callback is held in a ref so that passing an inline arrow function does not
  // restart the timer on every render. Restarting the interval every render is the
  // classic way a play button appears to do nothing.
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const total = Math.max(0, Number(frameCount) || 0);
  const lastIndex = Math.max(0, total - 1);

  // A new timeline rewinds. Without this, running a second algorithm while the
  // first is on screen would show frame 12 of a 4-frame run.
  useEffect(() => {
    setIndex(0);
    setPlaying(false);
    setCompleted(false);
  }, [frameCount]);

  useEffect(() => {
    if (!autoplay || total <= 1) return;
    setPlaying(true);
  }, [autoplay, total]);

  const goTo = useCallback(
    (next) => {
      const target = Math.min(lastIndex, Math.max(0, Number(next) || 0));
      setIndex(target);
      if (target >= lastIndex) setCompleted(true);
    },
    [lastIndex],
  );

  const stepForward = useCallback(() => {
    setIndex((current) => {
      const next = Math.min(lastIndex, current + 1);
      if (next >= lastIndex) setCompleted(true);
      return next;
    });
  }, [lastIndex]);

  const stepBackward = useCallback(() => {
    setPlaying(false);
    setCompleted(false);
    setIndex((current) => Math.max(0, current - 1));
  }, []);

  const togglePlay = useCallback(() => {
    // Pressing Play at the end rewinds rather than doing nothing. "Play" on a
    // finished timeline means "show me that again", and that is what it does.
    if (index >= lastIndex && total > 1) {
      setIndex(0);
      setCompleted(false);
      setPlaying(true);
      return;
    }
    setPlaying((current) => !current);
  }, [index, lastIndex, total]);

  const restart = useCallback(() => {
    setIndex(0);
    setCompleted(false);
  }, []);

  // The playback interval. Keyed on the speed so changing it restarts the timer at
  // the new interval rather than leaving the old one running.
  useEffect(() => {
    if (!playing || total <= 1) return undefined;
    const intervalMs = SPEEDS[speed]?.intervalMs ?? SPEEDS[DEFAULT_SPEED_INDEX].intervalMs;
    const timer = window.setInterval(() => {
      setIndex((current) => {
        const next = current + 1;
        if (next >= lastIndex) {
          setPlaying(false);
          setCompleted(true);
          return lastIndex;
        }
        return next;
      });
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [playing, speed, total, lastIndex]);

  useEffect(() => {
    if (completed) onCompleteRef.current?.();
  }, [completed]);

  return useMemo(
    () => ({
      index,
      total,
      lastIndex,
      playing,
      completed,
      speedIndex: speed,
      atStart: index <= 0,
      atEnd: total === 0 || index >= lastIndex,
      hasFrames: total > 0,
      progress: total > 1 ? index / lastIndex : 0,
      canStepForward: total > 1 && index < lastIndex,
      canStepBackward: total > 1 && index > 0,
      goTo,
      stepForward,
      stepBackward,
      togglePlay,
      restart,
      setSpeedIndex: (next) => setSpeed(Math.min(SPEEDS.length - 1, Math.max(0, Number(next) || 0))),
    }),
    [
      index,
      total,
      lastIndex,
      playing,
      completed,
      speed,
      goTo,
      stepForward,
      stepBackward,
      togglePlay,
      restart,
    ],
  );
}
