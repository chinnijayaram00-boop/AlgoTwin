import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Topbar from "./Topbar";
import { AuthProvider } from "../../features/auth/AuthProvider";
import { TOKEN_KEY } from "../../features/auth/authStorage";
import { authService } from "../../features/auth/authService";

vi.mock("../../features/auth/authService", () => ({
  authService: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
    register: vi.fn(),
  },
}));

const PROFILE = {
  id: 1,
  name: "Ada Lovelace",
  email: "ada@example.com",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderTopbar() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Topbar onMenu={() => {}} />
      </MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
  authService.logout.mockResolvedValue(null);
});

describe("Topbar account details", () => {
  it("shows the signed-in learner's name and email", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);

    renderTopbar();

    expect(await screen.findByText(PROFILE.name)).toBeInTheDocument();
    expect(screen.getByText(PROFILE.email)).toBeInTheDocument();
  });

  it("derives initials from the learner's name", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);

    const { container } = renderTopbar();

    await screen.findByText(PROFILE.name);
    expect(container.querySelector(".avatar")).toHaveTextContent("AL");
  });

  it("signs the learner out and forgets the session", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);
    const actor = userEvent.setup();

    renderTopbar();

    await screen.findByText(PROFILE.name);
    await actor.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(authService.logout).toHaveBeenCalledTimes(1));
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
