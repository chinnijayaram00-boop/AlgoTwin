import Editor from "@monaco-editor/react";
import { useCallback, useEffect, useRef } from "react";

// Imported for its side effect: it points the loader at the bundled editor and
// registers the language workers, before any `<Editor>` asks for the monaco instance.
import "./monacoSetup";

const EDITOR_OPTIONS = {
  automaticLayout: true,
  fontFamily: "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
  fontSize: 13,
  minimap: { enabled: false },
  padding: { top: 18, bottom: 18 },
  scrollBeyondLastLine: false,
  smoothScrolling: true,
  tabSize: 2,
};

/**
 * The Monaco code editor.
 *
 * Monaco is not self-sizing: it measures its container and lays out against whatever
 * it finds. Two things follow from that, and both were bugs here.
 *
 * The height has to be definite. `<Editor>` mounts at `height: 100%`, which resolves
 * against the nearest sized ancestor. The frame supplies one, so the editor gets real
 * pixels rather than a 0x0 box it can only paint as background.
 *
 * The layout has to be recomputed when the box changes. `automaticLayout` covers
 * ordinary resizes, but not the case where the editor mounts while the workspace is
 * hidden -- a collapsed tab, a hidden route, a container that was 0x0 at mount --
 * and it will keep that zero layout forever. So the mount, the language switch, and
 * any later size change each force `layout()`.
 */
export default function CodeEditor({ value, language, onChange }) {
  const containerRef = useRef(null);
  const editorRef = useRef(null);

  const relayout = useCallback(() => {
    editorRef.current?.layout();
  }, []);

  // A language swap changes the model's tokeniser and its diagnostics, so the
  // editor needs to be re-measured as well as re-typed.
  useEffect(() => {
    relayout();
  }, [language, relayout]);

  // Visibility. Monaco cannot measure a hidden container, and a workspace that was
  // hidden at mount keeps the measurements it took while it could not see itself.
  useEffect(() => {
    const onVisibilityChange = () => {
      if (!document.hidden) relayout();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [relayout]);

  // Container resize. `automaticLayout` already observes this, but an explicit
  // observer also covers the transition from 0x0 to a real size, which is the case
  // that leaves an editor permanently blank.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(() => relayout());
    observer.observe(container);
    return () => observer.disconnect();
  }, [relayout]);

  const handleMount = useCallback(
    (editor) => {
      editorRef.current = editor;
      editor.layout();
      // Open on the first line. Without this the editor can restore a scroll
      // position past the content and present as empty on a short buffer.
      editor.setScrollTop(0);
    },
    [],
  );

  return (
    <div className="editor-frame" ref={containerRef}>
      <Editor
        defaultLanguage={language}
        height="100%"
        language={language}
        loading={<div className="editor-frame-loading">Loading the editor…</div>}
        onChange={(nextValue) => onChange(nextValue || "")}
        onMount={handleMount}
        options={EDITOR_OPTIONS}
        theme="vs-dark"
        value={value}
        width="100%"
      />
    </div>
  );
}
