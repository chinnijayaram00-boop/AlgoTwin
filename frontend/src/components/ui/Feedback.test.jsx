import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPill } from "./Feedback";

describe("StatusPill", () => {
  it("renders its tone and label", () => {
    render(<StatusPill tone="success">Ready</StatusPill>);

    expect(screen.getByText("Ready")).toHaveClass("success");
  });
});
