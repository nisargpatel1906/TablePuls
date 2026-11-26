import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PublicDigitalMenu } from "@/components/PublicDigitalMenu";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const SAMPLE_PAYLOAD = {
  success: true,
  data: {
    venue: {
      name: "Spice Courtyard",
      tagline: "Wood-fired Bistro",
      logo_url: null,
      currency_code: "INR",
      timezone: "Asia/Kolkata",
    },
    table: { label: "Table T4" },
    menu_public_enabled: true,
    show_unavailable_items: true,
    preview_mode: false,
    menu_revision: 3,
    menus: [
      {
        id: "m1",
        name: "All Day",
        description: null,
        categories: [
          {
            id: "c1",
            name: "Starters",
            description: null,
            items: [
              {
                id: "i1",
                name: "Paneer Tikka",
                description: "Charred cottage cheese skewers",
                price_minor_units: 34900,
                compare_at_price_minor_units: 39900,
                image_url: null,
                thumb_url: null,
                image_alt: null,
                is_available: true,
                is_featured: true,
                dietary_tags: ["VEG"],
                allergens: ["DAIRY"],
                variants_json: [
                  { name: "Half", price_minor_units: 22000, is_available: true },
                  { name: "Full", price_minor_units: 34900, is_available: true },
                ],
                prep_time_minutes: 15,
                calories_kcal: 420,
              },
              {
                id: "i2",
                name: "Spicy Lamb Chops",
                description: "Crushed peppercorn crust",
                price_minor_units: 62000,
                compare_at_price_minor_units: null,
                image_url: null,
                thumb_url: null,
                image_alt: null,
                is_available: false,
                is_featured: false,
                dietary_tags: ["NON_VEG", "SPICY_HOT"],
                allergens: [],
                variants_json: [],
                prep_time_minutes: 25,
                calories_kcal: null,
              },
            ],
          },
        ],
      },
    ],
  },
};

describe("SCR-022 Public Digital Menu Isolation & Behavior", () => {
  it("fetches public endpoint with credentials=omit, filters dishes, and opens read-only detail sheet", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_PAYLOAD), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    render(<PublicDigitalMenu qrToken="tok_abc123" />);

    await waitFor(() => expect(screen.getByText("Spice Courtyard")).toBeTruthy());
    expect(screen.getByText("Table T4")).toBeTruthy();
    expect(screen.getByText("Paneer Tikka")).toBeTruthy();
    expect(screen.getByText("Spicy Lamb Chops")).toBeTruthy();

    // Verify strictly unauthenticated omit-credentials fetch
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("omit");

    // Filter by Veg chip hides Lamb Chops
    fireEvent.click(screen.getByRole("button", { name: "Veg" }));
    expect(screen.getByText("Paneer Tikka")).toBeTruthy();
    expect(screen.queryByText("Spicy Lamb Chops")).toBeNull();

    // Open dish detail bottom sheet -> shows allergens & variants without any cart/order controls
    fireEvent.click(screen.getByText("Paneer Tikka"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
    expect(screen.getByText("DAIRY")).toBeTruthy();
    expect(screen.getByText("Half")).toBeTruthy();
    expect(screen.queryByText(/add to cart|checkout/i)).toBeNull();
  });

  it("renders rotated/revoked QR polite screen on HTTP 410", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            error: { code: "QR_CODE_REVOKED", message: "Rotated" },
          }),
          { status: 410, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    render(<PublicDigitalMenu qrToken="tok_old" />);
    await waitFor(() => expect(screen.getByText("Table QR Replaced")).toBeTruthy());
  });
});
