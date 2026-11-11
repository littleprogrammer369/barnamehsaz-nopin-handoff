import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../src/components/ui";

describe("StatusBadge", () => {
  it("renders Persian labels for submission statuses", () => {
    const { unmount } = render(<StatusBadge status="draft" />);
    expect(screen.getByText("پیش‌نویس")).toBeInTheDocument();
    unmount();
  });

  it("renders a fallback for unknown statuses", () => {
    const { unmount } = render(<StatusBadge status="weird" />);
    expect(screen.getByText("weird")).toBeInTheDocument();
    unmount();
  });

  it("renders solver INFEASIBLE in Persian", () => {
    const { unmount } = render(<StatusBadge status="INFEASIBLE" />);
    expect(screen.getByText(/غیرممکن/)).toBeInTheDocument();
    unmount();
  });
});
