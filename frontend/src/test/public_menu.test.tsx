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

    // Mobile touch-target guarantees (>= 44px classes on header controls & dietary chips)
    expect(screen.getByRole("button", { name: "Toggle theme" }).className).toContain("h-11");
    expect(screen.getByRole("button", { name: "Toggle language" }).className).toContain("min-h-[44px]");
    expect(screen.getByRole("button", { name: "Veg" }).className).toContain("min-h-[44px]");

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

  it("localizes menu/category/item names in Hindi and loads paginated slices via headers", async () => {
    const baseMenu = SAMPLE_PAYLOAD.data.menus[0];
    const baseCat = baseMenu?.categories[0];
    const baseItem0 = baseCat?.items[0];
    const baseItem1 = baseCat?.items[1];
    if (!baseMenu || !baseCat || !baseItem0 || !baseItem1) {
      throw new Error("Missing sample menu fixture");
    }
    const page1 = {
      success: true,
      data: {
        ...SAMPLE_PAYLOAD.data,
        menus: [
          {
            ...baseMenu,
            translations_json: { hi: { name: "पूरा दिन" } },
            categories: [
              {
                ...baseCat,
                translations_json: { hi: { name: "स्टार्टर्स" } },
                items: [
                  {
                    ...baseItem0,
                    translations_json: {
                      hi: { name: "पनीर टिक्का", description: "तंदूरी पनीर" },
                    },
                  },
                ],
              },
            ],
          },
        ],
      },
    };
    const page2 = {
      success: true,
      data: {
        ...SAMPLE_PAYLOAD.data,
        menus: [
          {
            ...baseMenu,
            categories: [
              {
                ...baseCat,
                items: [
                  {
                    ...baseItem1,
                    translations_json: { hi: { name: "लैम्ब चॉप्स" } },
                  },
                ],
              },
            ],
          },
        ],
      },
    };
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(page1), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "X-Total-Items": "2",
            "X-Has-More": "true",
            "X-Next-Offset": "1",
          },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(page2), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "X-Total-Items": "2",
            "X-Has-More": "false",
          },
        }),
      );
    vi.stubGlobal("fetch", fetchSpy);

    render(<PublicDigitalMenu qrToken="tok_large" />);
    await waitFor(() => expect(screen.getByText("Paneer Tikka")).toBeTruthy());

    // Switch to Hindi -> localized names appear without extra fetch
    fireEvent.click(screen.getByRole("button", { name: "Toggle language" }));
    expect(screen.getByText("स्टार्टर्स")).toBeTruthy();
    expect(screen.getByText("पनीर टिक्का")).toBeTruthy();
    expect(screen.getByText("तंदूरी पनीर")).toBeTruthy();

    // Load page 2 progressively via X-Has-More / X-Next-Offset
    const moreBtn = screen.getByRole("button", { name: /और व्यंजन लोड करें/i });
    fireEvent.click(moreBtn);
    await waitFor(() => expect(screen.getByText("लैम्ब चॉप्स")).toBeTruthy());
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const secondCall = fetchSpy.mock.calls[1] as [string, RequestInit] | undefined;
    expect(String(secondCall?.[0])).toContain("offset=1&limit=100");
    expect(secondCall?.[1].credentials).toBe("omit");
  });
});
