import { describe, expect, it } from "vitest";
import { previewBulkCodes } from "@/app/venues/[venueId]/settings/tables/page";
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
});
