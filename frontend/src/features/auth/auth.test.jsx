import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import { AuthProvider } from "./AuthProvider";
import LoginPage from "./LoginPage";
import { TOKEN_KEY } from "./authStorage";
import { useAuth } from "./useAuth";
import { authService } from "./authService";

vi.mock("./authService", () => ({
  authService: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
    register: vi.fn(),
  },
}));

const PROFILE = { id: 1, name: "Ada Lovelace", email: "ada@example.com" };

function SessionProbe() {
  const { isAuthenticated, user } = useAuth();
  return <div>{isAuthenticated ? user.name : "anonymous"}</div>;
}

function LogoutProbe() {
  const { logout, user } = useAuth();
  return (
    <div>
      <span>{user?.name}</span>
      <button onClick={() => logout()} type="button">
        Sign out
      </button>
    </div>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("AuthProvider", () => {
  it("restores a session from a stored token", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );

    expect(await screen.findByText(PROFILE.name)).toBeInTheDocument();
    expect(authService.me).toHaveBeenCalled();
  });

  it("clears an unusable stored token", async () => {
    window.localStorage.setItem(TOKEN_KEY, "expired-token");
    authService.me.mockRejectedValue(new Error("Could not validate credentials."));

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("removes the stored token when signing out", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);
    authService.logout.mockResolvedValue(null);
    const actor = userEvent.setup();

    render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );

    await screen.findByText(PROFILE.name);
    await actor.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull());
    expect(authService.logout).toHaveBeenCalledTimes(1);
  });
});

describe("auth pages", () => {
  it("redirects anonymous visitors from the workspace to the login page", async () => {
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <App />
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByRole("heading", { name: /sign in to your workspace/i })).toBeInTheDocument();
  });

  it("stores the issued token and enters the workspace after login", async () => {
    const actor = userEvent.setup();
    authService.login.mockResolvedValue({
      access_token: "issued-token",
      token_type: "bearer",
      user: PROFILE,
    });

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route element={<LoginPage />} path="/login" />
            <Route element={<div>Workspace ready</div>} path="/dashboard" />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    await actor.type(await screen.findByLabelText("Email"), "ada@example.com");
    await actor.type(screen.getByLabelText("Password"), "correct-horse-battery-staple");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Workspace ready")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("issued-token");
    expect(authService.login).toHaveBeenCalledWith({
      email: "ada@example.com",
      password: "correct-horse-battery-staple",
    });
  });

  it("surfaces the API message when login fails", async () => {
    const actor = userEvent.setup();
    authService.login.mockRejectedValue(new Error("Invalid email or password."));

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route element={<LoginPage />} path="/login" />
            <Route element={<div>Workspace ready</div>} path="/dashboard" />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    await actor.type(await screen.findByLabelText("Email"), "ada@example.com");
    await actor.type(screen.getByLabelText("Password"), "wrong-password");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid email or password.")).toBeInTheDocument();
  });
});
