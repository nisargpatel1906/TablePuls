import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MenuItemDrawer } from "@/components/MenuItemDrawer";
import type { MenuCategoryDTO } from "@/types/floor";
import { nextAvailableTableCode, previewBulkCodes } from "@/lib/table-codes";
import {
  formatMinorUnits,
  minorUnitsToInputString,
  parseDisplayToMinorUnits,
} from "@/lib/currency";

describe("Phase 2 Currency & Table Utilities", () => {
  it("formats INR, USD, and zero-decimal JPY minor units cleanly", () => {
    expect(formatMinorUnits(34900, "INR", "en")).toContain("349");
    expect(formatMinorUnits(1250, "USD", "en")).toBe("$12.50");
    expect(formatMinorUnits(980, "JPY", "en")).toContain("980");
  });

  it("round-trips minor units to decimal input string and back without float drift", () => {
    expect(minorUnitsToInputString(1999, "USD")).toBe("19.99");
    expect(parseDisplayToMinorUnits("19.99", "USD")).toBe(1999);
    expect(parseDisplayToMinorUnits("0.1", "USD")).toBe(10);
    expect(minorUnitsToInputString(1500, "JPY")).toBe("1500");
    expect(parseDisplayToMinorUnits("1500", "JPY")).toBe(1500);
    expect(parseDisplayToMinorUnits("-5.00", "USD")).toBeNull();
  });

  it("generates bounded padded table code previews for bulk add", () => {
    expect(previewBulkCodes("p", 1, 3, 2)).toEqual(["P01", "P02", "P03"]);
    expect(previewBulkCodes("booth", 8, 2, 3)).toEqual(["BOOTH008", "BOOTH009"]);
    expect(previewBulkCodes("", 1, 5, 2)).toEqual([]);
  });

  it("allocates next unique table code across existing venue and camera tables", () => {
    expect(nextAvailableTableCode([])).toBe("T1");
    expect(nextAvailableTableCode(["T01", "T02", "T03", "T4"])).toBe("T5");
    expect(nextAvailableTableCode(["t1", "T2", "P01"])).toBe("T3");
  });

  it("preserves unsaved dish input in MenuItemDrawer when parent categories refresh (TC-P2-06 regression)", () => {
    const catA: MenuCategoryDTO = {
      id: "c1",
      venue_id: "v1",
      menu_id: "m1",
      name: "Chaat",
      description: null,
      is_active: true,
      sort_order: 0,
      item_count: 1,
    };
    const catsA: MenuCategoryDTO[] = [catA];
    const { rerender } = render(
      <MenuItemDrawer
        open
        venueId="v1"
        currencyCode="INR"
        categories={catsA}
        defaultCategoryId="c1"
        item={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const nameInput = screen.getByLabelText(/Dish Name/i) as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "Bombay Bhel Puri" } });

    // Simulate parent refetch creating a new categories array reference while drawer is open
    rerender(
      <MenuItemDrawer
        open
        venueId="v1"
        currencyCode="INR"
        categories={[{ ...catA, item_count: 2 }]}
        defaultCategoryId="c1"
        item={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect((screen.getByLabelText(/Dish Name/i) as HTMLInputElement).value).toBe("Bombay Bhel Puri");
  });
});
