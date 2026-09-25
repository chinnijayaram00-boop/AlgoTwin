import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import { AuthProvider } from "./AuthProvider";
import LoginPage from "./LoginPage";
import ProtectedRoute from "./ProtectedRoute";
import { TOKEN_KEY } from "./authStorage";
import { authService } from "./authService";
import { useAuth } from "./useAuth";

vi.mock("./authService", () => ({
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
const SESSION = { access_token: "issued-token", token_type: "bearer", expires_in: 3600, user: PROFILE };

function SessionProbe() {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return <div>loading</div>;
  return <div>{isAuthenticated ? `signed-in:${user?.name}` : "anonymous"}</div>;
}

function LogoutProbe() {
  const { isAuthenticated, logout, user } = useAuth();
  return (
    <div>
      <span>{isAuthenticated ? `signed-in:${user?.name}` : "anonymous"}</span>
      <button onClick={() => logout()} type="button">
        Sign out
      </button>
    </div>
  );
}

function withProvider(ui, { initialEntries = ["/"] } = {}) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
  authService.logout.mockResolvedValue(null);
});

// -------------------------------------------------------------- AuthProvider

describe("AuthProvider session restore", () => {
  it("restores a session from a stored token after a refresh", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);

    withProvider(<SessionProbe />);

    expect(await screen.findByText(`signed-in:${PROFILE.name}`)).toBeInTheDocument();
    expect(authService.me).toHaveBeenCalledTimes(1);
  });

  it("stays anonymous and skips the API call when no token is stored", async () => {
    withProvider(<SessionProbe />);

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(authService.me).not.toHaveBeenCalled();
  });

  it("clears an unusable stored token", async () => {
    window.localStorage.setItem(TOKEN_KEY, "expired-token");
    authService.me.mockRejectedValue(new Error("Could not validate credentials."));

    withProvider(<SessionProbe />);

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("removes the stored token when signing out", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);
    const actor = userEvent.setup();

    withProvider(<LogoutProbe />);

    await screen.findByText(`signed-in:${PROFILE.name}`);
    await actor.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(authService.logout).toHaveBeenCalledTimes(1);
  });

  it("clears the local session even when the logout call fails", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);
    authService.logout.mockRejectedValue(new Error("Network down"));
    const actor = userEvent.setup();

    withProvider(<LogoutProbe />);

    await screen.findByText(`signed-in:${PROFILE.name}`);
    await actor.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("does not revalidate a token it just issued", async () => {
    authService.login.mockResolvedValue(SESSION);
    const actor = userEvent.setup();

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route element={<LoginPage />} path="/login" />
            <Route element={<SessionProbe />} path="/dashboard" />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    await actor.type(await screen.findByLabelText("Email"), PROFILE.email);
    await actor.type(screen.getByLabelText("Password"), "correct-horse-battery-staple");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(`signed-in:${PROFILE.name}`)).toBeInTheDocument();
    // The session payload already carried the profile, so /auth/me is redundant.
    expect(authService.me).not.toHaveBeenCalled();
  });

  it("rejects a login response that carries no access token", async () => {
    authService.login.mockResolvedValue({ user: PROFILE });
    const actor = userEvent.setup();

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route element={<LoginPage />} path="/login" />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    await actor.type(await screen.findByLabelText("Email"), PROFILE.email);
    await actor.type(screen.getByLabelText("Password"), "correct-horse-battery-staple");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/did not include an access token/i)).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});

// ------------------------------------------------------------- routing guards

describe("route protection", () => {
  it("redirects anonymous visitors from a protected page to the login form", async () => {
    withProvider(<App />, { initialEntries: ["/dashboard"] });

    expect(await screen.findByRole("heading", { name: /sign in to your workspace/i })).toBeInTheDocument();
  });

  it("protects every workspace page, not just the dashboard", async () => {
    for (const path of ["/problems", "/analytics", "/settings", "/visualizer"]) {
      window.localStorage.clear();
      const view = withProvider(<App />, { initialEntries: [path] });
      expect(await screen.findByRole("heading", { name: /sign in to your workspace/i })).toBeInTheDocument();
      view.unmount();
    }
  });

  it("returns the user to the page they originally requested", async () => {
    authService.login.mockResolvedValue(SESSION);
    const actor = userEvent.setup();

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/problems"]}>
          <Routes>
            <Route element={<ProtectedRoute><p>Private</p></ProtectedRoute>} path="*" />
            <Route element={<LoginPage />} path="/login" />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByRole("heading", { name: /sign in to your workspace/i })).toBeInTheDocument();
    await actor.type(screen.getByLabelText("Email"), PROFILE.email);
    await actor.type(screen.getByLabelText("Password"), "correct-horse-battery-staple");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Private")).toBeInTheDocument();
  });

  it("keeps a signed-in user away from the login and register forms", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    authService.me.mockResolvedValue(PROFILE);

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <App />
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /sign in to your workspace/i })).not.toBeInTheDocument();
  });

  it("shows a restoring state instead of redirecting while the token is validated", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    let release;
    authService.me.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve(PROFILE);
        }),
    );

    withProvider(<App />, { initialEntries: ["/dashboard"] });

    expect(await screen.findByRole("status")).toHaveTextContent("Restoring your session");
    expect(screen.queryByRole("heading", { name: /sign in to your workspace/i })).not.toBeInTheDocument();

    release();
    expect(await screen.findByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- login page

describe("LoginPage", () => {
  function renderLogin(initialEntries = ["/login"]) {
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route element={<LoginPage />} path="/login" />
            <Route element={<div>Workspace ready</div>} path="/dashboard" />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );
  }

  it("stores the issued token and enters the workspace", async () => {
    authService.login.mockResolvedValue(SESSION);
    const actor = userEvent.setup();
    renderLogin();

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

  it("trims the email before sending it", async () => {
    authService.login.mockResolvedValue(SESSION);
    const actor = userEvent.setup();
    renderLogin();

    await actor.type(await screen.findByLabelText("Email"), "  ada@example.com  ");
    await actor.type(screen.getByLabelText("Password"), "correct-horse-battery-staple");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(authService.login).toHaveBeenCalledWith({
      email: "ada@example.com",
      password: "correct-horse-battery-staple",
    });
  });

  it("surfaces the API message when the password is wrong", async () => {
    authService.login.mockRejectedValue(new Error("Invalid email or password."));
    const actor = userEvent.setup();
    renderLogin();

    await actor.type(await screen.findByLabelText("Email"), "ada@example.com");
    await actor.type(screen.getByLabelText("Password"), "wrong-password");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid email or password.")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("shows a duplicate-account message on register", async () => {
    authService.login.mockRejectedValue(new Error("An account with that email already exists."));
    const actor = userEvent.setup();
    renderLogin();

    await actor.type(await screen.findByLabelText("Email"), "ada@example.com");
    await actor.type(screen.getByLabelText("Password"), "correct-horse-battery-staple");
    await actor.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("An account with that email already exists.")).toBeInTheDocument();
  });

  it("links to the register page", async () => {
    renderLogin();

    expect(await screen.findByRole("link", { name: /create an account/i })).toHaveAttribute("href", "/register");
  });
});
