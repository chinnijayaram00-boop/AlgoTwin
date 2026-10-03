import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CodeEditor from "./CodeEditor";

/**
 * Monaco cannot run under jsdom -- it needs real layout, a real font metrics engine,
 * and a worker -- so it is mocked here. What these tests pin is the contract the
 * component hands it: the size it is given, the value it is given, and the calls it
 * makes to re-measure itself.
 *
 * That contract is the whole bug. Monaco lays out against whatever box it is given
 * and never corrects it on its own, so an editor mounted into a container without a
 * definite height stays 0x0 forever and renders nothing at all -- no text, no cursor,
 * no error. These assertions are the regression guard for that.
 */

// The side-effectful setup imports the real editor bundle and Vite worker queries,
// which jsdom cannot load. Its job is exercised by the build, not here.
vi.mock("./monacoSetup", () => ({}));

const editor = {
  layout: vi.fn(),
  setScrollTop: vi.fn(),
  focus: vi.fn(),
};

let handed;

vi.mock("@monaco-editor/react", () => ({
  default: ({ loading, onMount, ...props }) => {
    handed = props;
    onMount(editor);
    return (
      <div
        data-language={props.language}
        data-testid="monaco-editor"
        data-value={props.value}
        data-width={props.width}
      >
        {loading}
      </div>
    );
  },
}));

class FakeResizeObserver {
  static instances = [];

  constructor(callback) {
    this.callback = callback;
    FakeResizeObserver.instances.push(this);
  }

  observe() {}

  disconnect() {
    this.disconnected = true;
  }

  trigger() {
    this.callback([]);
  }
}

beforeEach(() => {
  handed = null;
  editor.layout.mockClear();
  editor.setScrollTop.mockClear();
  FakeResizeObserver.instances = [];
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CodeEditor", () => {
  it("mounts the editor inside the frame that sizes it", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="const a = 1;" />);

    expect(screen.getByTestId("monaco-editor")).toBeInTheDocument();
    expect(screen.getByTestId("monaco-editor").closest(".editor-frame")).toBeTruthy();
  });

  it("gives the editor a height to lay out into", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="" />);

    // Not a pixel count: `100%` against a frame with a definite height is what lets
    // the editor fill the panel and resize with it. Passing nothing here is what
    // left the workspace with a blank rectangle.
    expect(handed.height).toBe("100%");
    expect(handed.width).toBe("100%");
  });

  it("keeps the automatic layout option on, so ordinary resizes are not ours to miss", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="" />);

    expect(handed.options.automaticLayout).toBe(true);
    expect(handed.theme).toBe("vs-dark");
  });

  it("shows the current buffer", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="function solve() {}" />);

    expect(screen.getByTestId("monaco-editor").dataset.value).toBe("function solve() {}");
  });

  it("reports edits, and never an undefined buffer", () => {
    const onChange = vi.fn();
    render(<CodeEditor language="javascript" onChange={onChange} value="" />);

    act(() => handed.onChange("let x = 2;"));
    expect(onChange).toHaveBeenCalledWith("let x = 2;");

    // Monaco reports `undefined` when the buffer is emptied by select-all-delete.
    // Left as undefined, `value` becomes uncontrolled and the editor stops tracking
    // the problem's own state, so Reset silently does nothing.
    onChange.mockClear();
    act(() => handed.onChange(undefined));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("measures itself as soon as it mounts", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="" />);

    expect(editor.layout).toHaveBeenCalled();
    expect(editor.setScrollTop).toHaveBeenCalledWith(0);
  });

  it("measures itself again when the language changes", () => {
    const { rerender } = render(
      <CodeEditor language="javascript" onChange={() => {}} value="" />,
    );
    editor.layout.mockClear();

    rerender(<CodeEditor language="python" onChange={() => {}} value="" />);

    expect(screen.getByTestId("monaco-editor").dataset.language).toBe("python");
    // The model is re-created for the new language, and a re-created model keeps the
    // old one's dimensions unless the editor is told to re-measure.
    expect(editor.layout).toHaveBeenCalled();
  });

  it("measures itself when the frame is resized", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="" />);
    editor.layout.mockClear();

    act(() => FakeResizeObserver.instances[0].trigger());

    expect(editor.layout).toHaveBeenCalled();
  });

  it("stops observing the frame when it unmounts", () => {
    const { unmount } = render(<CodeEditor language="javascript" onChange={() => {}} value="" />);

    unmount();

    expect(FakeResizeObserver.instances[0].disconnected).toBe(true);
  });

  it("measures itself when the workspace becomes visible again", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="" />);
    editor.layout.mockClear();

    // Hidden at mount is the case `automaticLayout` cannot rescue: monaco measured
    // nothing, and a tab switch back to the page would otherwise leave it blank.
    act(() => {
      Object.defineProperty(document, "hidden", { configurable: true, value: true });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(editor.layout).not.toHaveBeenCalled();

    act(() => {
      Object.defineProperty(document, "hidden", { configurable: true, value: false });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(editor.layout).toHaveBeenCalled();

    Object.defineProperty(document, "hidden", { configurable: true, value: false });
  });

  it("says it is loading rather than showing an empty panel", () => {
    render(<CodeEditor language="javascript" onChange={() => {}} value="" />);

    // `@monaco-editor/react` renders nothing at all while monaco is starting up,
    // which is indistinguishable from the editor having failed to load.
    expect(screen.getByText(/loading the editor/i)).toBeInTheDocument();
  });

  it("works without a ResizeObserver in the environment", () => {
    vi.stubGlobal("ResizeObserver", undefined);

    expect(() =>
      render(<CodeEditor language="javascript" onChange={() => {}} value="" />),
    ).not.toThrow();
  });
});

describe("the frame the editor mounts into", () => {
  // Vitest runs from the frontend workspace, so the stylesheet is one level of
  // `src` away. Reading it here is the only way to assert the rule: jsdom does not
  // compute layout, so a CSS regression is invisible to every other test in the file.
  const stylesheet = readFileSync(resolve(process.cwd(), "src/styles/global.css"), "utf8");

  function ruleFor(selector) {
    const match = stylesheet.match(new RegExp(`^\\.${selector}\\s*\\{([^}]*)\\}`, "m"));
    return match ? match[1] : "";
  }

  it("carries a definite height, not only a minimum", () => {
    const frame = ruleFor("editor-frame");

    // This is the regression, asserted at the level it happened. `min-height` leaves
    // the parent's height indefinite, so the editor's `height: 100%` resolves to
    // `auto` and monaco lays out into nothing. jsdom cannot compute this, which is
    // why the stylesheet has to be read directly.
    expect(frame).toMatch(/(^|;)\s*height\s*:/);
    expect(frame).not.toMatch(/(^|;)\s*height\s*:\s*auto/);
  });

  it("keeps a floor tall enough to write a solution in", () => {
    expect(ruleFor("editor-frame")).toMatch(/min-height\s*:\s*4\d\dpx/);
  });
});
