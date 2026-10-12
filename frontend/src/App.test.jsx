import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthProvider } from "./features/auth/AuthProvider";

/**
 * Route-level code splitting, guarded.
 *
 * `App` reaches the code workspace only through a dynamic import, so loading its
 * module tree must not evaluate the editor setup. The setup module is the one
 * `features/problems/CodeEditor` imports for its side effect, and it is the root
 * of the whole heavy subtree -- Monaco plus its language workers. Instrumenting
 * it is the observable half of the same property the build measures: the initial
 * bundle shrank from 4,959 kB to a couple of hundred because that subtree became
 * a lazy chunk. A page pulled back into `App` with a static import would evaluate
 * this module during the import below and the assertion would fail.
 */
const editorSetup = vi.hoisted(() => ({ loaded: false }));

vi.mock("./features/problems/monacoSetup", () => {
  editorSetup.loaded = true;
  return {};
});

vi.mock("./features/auth/authService", () => ({
  authService: { login: vi.fn(), logout: vi.fn(), me: vi.fn(), register: vi.fn() },
}));

beforeEach(() => {
  window.localStorage.clear();
});

describe("route-level code splitting", () => {
  it("does not evaluate the editor setup until the workspace route is opened", async () => {
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <App />
        </MemoryRouter>
      </AuthProvider>,
    );

    // Anonymous visitors are redirected by the guard, so the dashboard chunk is
    // never requested and the editor subtree is never touched.
    expect(
      await screen.findByRole("heading", { name: /sign in to your workspace/i }),
    ).toBeInTheDocument();
    expect(editorSetup.loaded).toBe(false);
  });
});
