import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthProvider";
import RegisterPage from "./RegisterPage";
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
  id: 7,
  name: "Grace Hopper",
  email: "grace@example.com",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const SESSION = { access_token: "new-account-token", token_type: "bearer", expires_in: 3600, user: PROFILE };
const PASSWORD = "correct-horse-battery-staple";

function SessionProbe() {
  const { isAuthenticated, user } = useAuth();
  return <div>{isAuthenticated ? `signed-in:${user?.name}` : "anonymous"}</div>;
}

function renderRegister() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/register"]}>
        <Routes>
          <Route element={<RegisterPage />} path="/register" />
          <Route element={<SessionProbe />} path="/dashboard" />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

async function fillForm(actor, { email = "grace@example.com", password = PASSWORD } = {}) {
  await actor.type(await screen.findByLabelText("Full name"), "Grace Hopper");
  await actor.type(screen.getByLabelText("Email"), email);
  await actor.type(screen.getByLabelText("Password"), password);
}

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe("RegisterPage", () => {
  it("creates the account, stores the token, and enters the workspace", async () => {
    authService.register.mockResolvedValue(SESSION);
    const actor = userEvent.setup();
    renderRegister();

    await fillForm(actor);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText(`signed-in:${PROFILE.name}`)).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("new-account-token");
    expect(authService.register).toHaveBeenCalledWith({
      name: "Grace Hopper",
      email: "grace@example.com",
      password: PASSWORD,
    });
  });

  it("trims the name and email before sending them", async () => {
    authService.register.mockResolvedValue(SESSION);
    const actor = userEvent.setup();
    renderRegister();

    await actor.type(await screen.findByLabelText("Full name"), "  Grace Hopper  ");
    await actor.type(screen.getByLabelText("Email"), "  grace@example.com  ");
    await actor.type(screen.getByLabelText("Password"), PASSWORD);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(authService.register).toHaveBeenCalledWith({
      name: "Grace Hopper",
      email: "grace@example.com",
      password: PASSWORD,
    });
  });

  it("surfaces a duplicate-email rejection from the API", async () => {
    authService.register.mockRejectedValue(new Error("An account with that email already exists."));
    const actor = userEvent.setup();
    renderRegister();

    await fillForm(actor);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("An account with that email already exists.")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(screen.getByRole("heading", { name: /create your learner profile/i })).toBeInTheDocument();
  });

  it("surfaces a validation error message returned by the API", async () => {
    // Passes the client-side rules, so the rejection must come from the server.
    authService.register.mockRejectedValue(new Error("email: value is not a valid email address"));
    const actor = userEvent.setup();
    renderRegister();

    await fillForm(actor);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("email: value is not a valid email address")).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("re-enables the submit button after a failed attempt", async () => {
    authService.register.mockRejectedValue(new Error("Invalid email or password."));
    const actor = userEvent.setup();
    renderRegister();

    await fillForm(actor);
    const submit = screen.getByRole("button", { name: "Create account" });
    await actor.click(submit);

    expect(await screen.findByRole("button", { name: "Create account" })).toBeEnabled();
  });

  it("blocks submission of a password shorter than the policy", async () => {
    const actor = userEvent.setup();
    renderRegister();

    await fillForm(actor, { password: "short" });
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText(/must be at least 10 characters/i)).toBeInTheDocument();
    expect(authService.register).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("blocks submission of a malformed email before calling the API", async () => {
    const actor = userEvent.setup();
    renderRegister();

    await actor.type(await screen.findByLabelText("Full name"), "Grace Hopper");
    await actor.type(screen.getByLabelText("Email"), "not-an-email");
    await actor.type(screen.getByLabelText("Password"), PASSWORD);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(authService.register).not.toHaveBeenCalled();
  });

  it("blocks submission when the name is only whitespace", async () => {
    const actor = userEvent.setup();
    renderRegister();

    await actor.type(await screen.findByLabelText("Full name"), "   ");
    await actor.type(screen.getByLabelText("Email"), "grace@example.com");
    await actor.type(screen.getByLabelText("Password"), PASSWORD);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText(/enter your name/i)).toBeInTheDocument();
    expect(authService.register).not.toHaveBeenCalled();
  });

  it("replaces a stale error once the form is corrected", async () => {
    authService.register.mockRejectedValue(new Error("An account with that email already exists."));
    const actor = userEvent.setup();
    renderRegister();

    await fillForm(actor);
    await actor.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("An account with that email already exists.")).toBeInTheDocument();

    authService.register.mockResolvedValue(SESSION);
    await actor.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText(`signed-in:${PROFILE.name}`)).toBeInTheDocument();
  });

  it("requires a name, an email, and a password", async () => {
    renderRegister();

    expect(await screen.findByLabelText("Full name")).toBeRequired();
    expect(screen.getByLabelText("Email")).toBeRequired();
    expect(screen.getByLabelText("Password")).toBeRequired();
  });

  it("states the password policy in the form", async () => {
    renderRegister();

    expect(await screen.findByText(/at least 10 characters/i)).toBeInTheDocument();
  });

  it("offers the correct autofill hints for the browser", async () => {
    renderRegister();

    expect(await screen.findByLabelText("Full name")).toHaveAttribute("autocomplete", "name");
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
  });

  it("links back to the login page", async () => {
    renderRegister();

    expect(await screen.findByRole("link", { name: /sign in instead/i })).toHaveAttribute("href", "/login");
  });
});
